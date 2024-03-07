#include "rowhammer/counter_cache/rh_secure_module.hh"
#include <iostream>

#include "base/trace.hh"
#include "debug/RhSecureModule.hh"
#include "debug/RhSecureModuleCpp.hh"
#include "debug/RhSecureModuleCycles.hh"

namespace gem5
{

  // constructor
  RhSecureModule::RhSecureModule(const RhSecureModuleParams &params)
      : ClockedObject(params), waitingPortId(-1),
        cpuPort(params.name + ".cpu_side", this),
        memPort(params.name + ".mem_side", this),
        mem_issue_latency(params.mem_issue_latency),
        read_issue_latency(params.read_issue_latency),
        write_issue_latency(params.write_issue_latency),
        // dram_avg_access_latency(params.dram_avg_access_latency),
        responseQueue(params.response_queue_size),
        requestQueue(params.request_queue_size),
        stats(this)
  // requestQueue(params.queue_size),
  {
    cpuWaiting = false;
    pendingRequest = false;
    pendingResponse = false;

    cpuBlocked = false;
    memBlocked = false;
    std::srand(0);
  }

  // unimplemented, nothing needs to be done here
  void RhSecureModule::startup()
  {
    DPRINTF(RhSecureModuleCpp, "startup\n");
    schedule(new EventFunctionWrapper([this]
                                      { cycle(); },
                                      name() + ".startupEvent", true),
             clockEdge(Cycles(1)));
  }

  // on every cycle, we check if we have any packets to send to the cpu or memory
  void RhSecureModule::cycle()
  {
    // print size of both queues and pending flags, all in one line
    DPRINTF(RhSecureModuleCycles, "requestQueue.size: %d, responseQueue.size: %d, pendingRequest: %d, pendingResponse: %d\n", requestQueue.size(), responseQueue.size(), pendingRequest, pendingResponse);

    if (!requestQueue.empty() && *std::get<1>(requestQueue.front()) == true)
    {
      DPRINTF(RhSecureModuleCpp, "requestQueue.front() is ready\n");
      memPort.sendPacketQueue();
    }
    // try to send repsonses
    if (!responseQueue.empty())
    {
      cpuPort.sendPacketQueue();
    }

    // other things that should just happen every cycle
    handleCpuReqRetry();
    handleMemRespRetry();

    // invoke on the next cycle, keep this going.
    // do we need to make sure this stops at some point?
    schedule(new EventFunctionWrapper([this]
                                      { cycle(); },
                                      name() + ".startupEvent", true),
             clockEdge(Cycles(1)));
  }

  Port &RhSecureModule::getPort(const std::string &if_name, PortID idx)
  {
    DPRINTF(RhSecureModuleCpp, "getPort %s\n", if_name);

    if (if_name == "mem_side")
    {
      return memPort;
    }
    else if (if_name == "cpu_side")
    {
      return cpuPort;
    }
    else
    {
      // i don't really know what happens at this point...
      // tbd when a stack trace points here
      panic("returning neither a cpu nor mem port...");
      return ClockedObject::getPort(if_name, idx);
    }
  }

  AddrRangeList RhSecureModule::CPUSidePort::getAddrRanges() const
  {
    DPRINTF(RhSecureModuleCpp, "getAddrRanges\n");
    return owner->getAddrRanges();
  }

  bool RhSecureModule::CPUSidePort::sendPacket(PacketPtr pkt)
  {
    DPRINTF(RhSecureModuleCpp, "Sending packet: %s\n", pkt->print());

    // If we can't send the packet across the port, store it for later.
    // logic for package trasmission should be minimal
    bool success = sendTimingResp(pkt);
    return success;
  }

  bool RhSecureModule::CPUSidePort::sendPacketQueue()
  {
    DPRINTF(RhSecureModuleCpp, "sendPacketQueue\n");
    DPRINTF(RhSecureModuleCpp, "responseQueue.size: %d\n", owner->responseQueue.size());

    if (owner->cpuBlocked)
    {
      DPRINTF(RhSecureModuleCpp, "⚠️ CPU is blocked. Need to wait for a retry before attempting\n");
      return false;
    }
    if (owner->responseQueue.empty())
    {
      DPRINTF(RhSecureModuleCpp, "⚠️ responseQueue is empty. nothing to send\n");
      return false;
    }

    PacketPtr pkt = owner->responseQueue.front();
    bool succ = sendTimingResp(pkt);
    if (!succ) // return false, retry request will come later
    {
      DPRINTF(RhSecureModuleCpp, "❌ CPU denied packet %s\n", pkt->print());
      owner->cpuBlocked = true;
    }
    else
    { // succesful send
      owner->responseQueue.pop();
      DPRINTF(RhSecureModuleCpp, "✅ CPU accepted packet %s\n", pkt->print());
    }
    return succ;
  }

  void RhSecureModule::CPUSidePort::recvFunctional(PacketPtr pkt)
  {
    // DPRINTF(RhSecureModuleCpp, "recvFunctional\n");
    // Just forward to the memobj.
    return owner->handleFunctional(pkt);
  }

  bool RhSecureModule::CPUSidePort::recvTimingReq(PacketPtr pkt)
  {
    DPRINTF(RhSecureModuleCpp, "➡️️recvTimingReq, pkt-> %s\n", pkt->print());
    return owner->handleRequest(pkt);
  }

  void RhSecureModule::CPUSidePort::recvRespRetry()
  {
    DPRINTF(RhSecureModuleCpp, "recvRespRetry\n");
    owner->pendingRequest = false;
    owner->cpuBlocked = false;
  }

  // PLAN TO DEPRECATE
  bool RhSecureModule::MemSidePort::sendPacket(PacketPtr pkt)
  {
    DPRINTF(RhSecureModuleCpp, "sendPacket\n");
    bool succ = sendTimingReq(pkt);
    if (!succ) // return false, retry request will come later
    {
      DPRINTF(RhSecureModuleCpp, "memory denied packet, entering state MEM_WAITING_RETRY\n");
      DPRINTF(RhSecureModuleCpp, "❌ Memory denied packet %s", pkt->print());
    }
    else
    { // succesful send
      DPRINTF(RhSecureModuleCpp, "✅ Memory accepted packet %s\n", pkt->print());
    }
    return succ;
  }

  // similar to regular sendpacket, references request queue instead of a single packet
  bool RhSecureModule::MemSidePort::sendPacketQueue()
  {
    DPRINTF(RhSecureModuleCpp, "sendPacketQueue\n");
    DPRINTF(RhSecureModuleCpp, "requestQueue.size: %d\n", owner->requestQueue.size());

    if (owner->memBlocked)
    {
      DPRINTF(RhSecureModuleCpp, "Memory is blocked. Need to wait for a retry before attempting\n");
      return false;
    }
    if (owner->requestQueue.empty())
    {
      DPRINTF(RhSecureModuleCpp, "⚠️ requestQueue is empty. nothing to send\n");
      return false;
    }

    PacketPtr pkt = std::get<0>(owner->requestQueue.front());
    bool succ = sendTimingReq(pkt);
    if (!succ) // return false, retry request will come later
    {
      DPRINTF(RhSecureModuleCpp, "memory denied packet, entering state MEM_WAITING_RETRY\n");
      DPRINTF(RhSecureModuleCpp, "❌ Memory denied packet %s", pkt->print());
      owner->memBlocked = true;
    }
    else
    { // succesful send
      owner->requestQueue.pop();
      DPRINTF(RhSecureModuleCpp, "✅ Memory accepted packet %s\n", pkt->print());
    }
    return succ;
  }

  bool RhSecureModule::MemSidePort::recvTimingResp(PacketPtr pkt)
  {
    DPRINTF(RhSecureModuleCpp, "⬅️ recvTimingResp\n");
    return owner->handleResponse(pkt);
  }

  void RhSecureModule::MemSidePort::recvReqRetry()
  {
    DPRINTF(RhSecureModuleCpp, "recvReqRetry\n");
    owner->pendingResponse = false;
    owner->memBlocked = false;

    sendPacketQueue();
  }

  void RhSecureModule::MemSidePort::recvRangeChange()
  {
    DPRINTF(RhSecureModuleCpp, "recvRangeChange\n");
    owner->sendRangeChange();
  }

  // secure module main methods
  void RhSecureModule::handleCpuReqRetry()
  {
    if (pendingRequest)
    {
      DPRINTF(RhSecureModuleCpp, "Sending CPU request retry\n");
      pendingRequest = false;
      cpuPort.sendRetryReq();
      return;
    }
  }

  void RhSecureModule::handleMemRespRetry()
  {
    if (pendingResponse)
    {
      DPRINTF(RhSecureModuleCpp, "Sending MEM response retry\n");
      pendingResponse = false;
      memPort.sendRetryResp();
      return;
    }
  }

  bool RhSecureModule::handleRequest(PacketPtr pkt)
  {
    DPRINTF(RhSecureModule, "%s for addr %#x\n", pkt->cmdString(), pkt->getAddr());
    DPRINTF(RhSecureModuleCpp, "handleRequest . pkt-type: %s for addr %#x\n", pkt->cmdString(), pkt->getAddr());

    bool *b = new bool(false);
    std::tuple<PacketPtr, bool *> p = std::make_tuple(pkt, b);
    bool succ = requestQueue.push(p);
    if (!succ)
    {
      DPRINTF(RhSecureModuleCpp, "enqueueRequest failed\n");
      pendingRequest = true;
    }
    else
    {
      pendingRequest = false; // by virtue of the queue having space
      DPRINTF(RhSecureModuleCpp, "enqueueRequest success\n");
      // add to the event queue to process a request from the queue

      Tick read_delay = clockEdge(mem_issue_latency + read_issue_latency + static_cast<Cycles>(1));
      Tick write_delay = clockEdge(mem_issue_latency + write_issue_latency + static_cast<Cycles>(1));

      if (pkt->cmdString().find("Read"))
      {
        stats.readReqs++;
        DPRINTF(RhSecureModuleCpp, "Read req: scheduling for tick %d\n", read_delay);
        schedule(new EventFunctionWrapper([this, b]
                                          { setPacketReady(b); },
                                          name() + ".accessEvent", true),
                 read_delay); // TODO: update this hardcoded value to a param
      }
      else if (pkt->cmdString().find("Write"))
      {
        stats.writeReqs++;
        DPRINTF(RhSecureModuleCpp, "Write req: scheduling for tick %d\n", write_delay);
        schedule(new EventFunctionWrapper([this, b]
                                          { setPacketReady(b); },
                                          name() + ".accessEvent", true),
                 write_delay); // TODO: update this hardcoded value to a param
      }
      else
      {
        fatal("Unknown packet type: %s\n", pkt->cmdString());
      }
    }
    return succ;
  }

  bool RhSecureModule::handleResponse(PacketPtr pkt)
  {
    DPRINTF(RhSecureModule, "Got response for addr %#x\n", pkt->getAddr());
    DPRINTF(RhSecureModuleCpp, "handleResponse. pkt-type: %s\n", pkt->cmdString());

    // we got here because memPort.recvTimingResp was called.
    // either we succesfully add pkt to respons queue or we return false to sender
    // and ask for a retry later when we're ready
    bool succ = responseQueue.push(pkt);
    if (!succ)
    {
      DPRINTF(RhSecureModuleCpp, "enqueueResponse failed\n");
      pendingResponse = true;
    }
    else
    {
      pendingResponse = false; // by virtue of the queue having space
      DPRINTF(RhSecureModuleCpp, "enqueueResponse success\n");
    }
    return succ;
  }

  void RhSecureModule::setPacketReady(bool *b)
  {
    // simple function that sets a flag to true
    DPRINTF(RhSecureModuleCpp, "setPacketReady\n");
    *b = true;
  }

  void RhSecureModule::cleanReady()
  {
    DPRINTF(RhSecureModuleCpp, "cleanReady\n");
    // should not execute here if we are not in the ready state
    if (cpuWaiting)
    {
      DPRINTF(RhSecureModuleCpp, "sendingRetyReq\n");
      cpuPort.sendRetryReq();
    }
  }

  void RhSecureModule::handleFunctional(PacketPtr pkt)
  {
    // DPRINTF(RhSecureModuleCpp, "handleFunctional\n");
    // Just pass this on to the memory side to handle for now.
    memPort.sendFunctional(pkt);
  }

  AddrRangeList RhSecureModule::getAddrRanges() const
  {
    DPRINTF(RhSecureModuleCpp, "getAddrRanges\n");
    DPRINTF(RhSecureModule, "Sending new ranges\n");
    // Just use the same ranges as whatever is on the memory side.
    return memPort.getAddrRanges();
  }

  void RhSecureModule::sendRangeChange()
  {
    DPRINTF(RhSecureModuleCpp, "sendRangeChange\n");
    cpuPort.sendRangeChange();
  }
  // atomics
  Tick RhSecureModule::CPUSidePort::recvAtomic(PacketPtr pkt)
  {
    DPRINTF(RhSecureModuleCpp, "recvAtomic\n");
    Tick tick = owner->memPort.sendAtomic(pkt);
    return tick;
  }

  RhSecureModule::RhSecureModuleStats::RhSecureModuleStats(statistics::Group *parent)
      : statistics::Group(parent),
        ADD_STAT(readReqs, statistics::units::Count::get(), "Number of read requests"),
        ADD_STAT(writeReqs, statistics::units::Count::get(), "Number of write requests")
  {
    // do nothing:
  }

} // namespace gem5
