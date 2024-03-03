#include "rowhammer/counter_cache/counter_cache.hh"

#include <iostream>

#include "base/trace.hh"
#include "debug/CounterCache.hh"
#include "debug/CounterCacheCpp.hh"
#include "debug/CounterCacheCycles.hh"

namespace gem5
{

  // constructor
  CounterCache::CounterCache(const CounterCacheParams &params)
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
  void CounterCache::startup()
  {
    DPRINTF(CounterCacheCpp, "startup\n");
    schedule(new EventFunctionWrapper([this]
                                      { cycle(); },
                                      name() + ".startupEvent", true),
             clockEdge(Cycles(1)));
  }

  // on every cycle, we check if we have any packets to send to the cpu or memory
  void CounterCache::cycle()
  {
    // print size of both queues and pending flags, all in one line
    DPRINTF(CounterCacheCycles, "requestQueue.size: %d, responseQueue.size: %d, pendingRequest: %d, pendingResponse: %d\n", requestQueue.size(), responseQueue.size(), pendingRequest, pendingResponse);

    if (!requestQueue.empty() && *std::get<1>(requestQueue.front()) == true)
    {
      DPRINTF(CounterCacheCpp, "requestQueue.front() is ready\n");
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

  Port &CounterCache::getPort(const std::string &if_name, PortID idx)
  {
    DPRINTF(CounterCacheCpp, "getPort %s\n", if_name);

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

  AddrRangeList CounterCache::CPUSidePort::getAddrRanges() const
  {
    DPRINTF(CounterCacheCpp, "getAddrRanges\n");
    return owner->getAddrRanges();
  }

  bool CounterCache::CPUSidePort::sendPacket(PacketPtr pkt)
  {
    DPRINTF(CounterCacheCpp, "Sending packet: %s\n", pkt->print());

    // If we can't send the packet across the port, store it for later.
    // logic for package trasmission should be minimal
    bool success = sendTimingResp(pkt);
    return success;
  }

  bool CounterCache::CPUSidePort::sendPacketQueue()
  {
    DPRINTF(CounterCacheCpp, "sendPacketQueue\n");
    DPRINTF(CounterCacheCpp, "responseQueue.size: %d\n", owner->responseQueue.size());

    if (owner->cpuBlocked)
    {
      DPRINTF(CounterCacheCpp, "⚠️ CPU is blocked. Need to wait for a retry before attempting\n");
      return false;
    }
    if (owner->responseQueue.empty())
    {
      DPRINTF(CounterCacheCpp, "⚠️ responseQueue is empty. nothing to send\n");
      return false;
    }

    PacketPtr pkt = owner->responseQueue.front();
    bool succ = sendTimingResp(pkt);
    if (!succ) // return false, retry request will come later
    {
      DPRINTF(CounterCacheCpp, "❌ CPU denied packet %s\n", pkt->print());
      owner->cpuBlocked = true;
    }
    else
    { // succesful send
      owner->responseQueue.pop();
      DPRINTF(CounterCacheCpp, "✅ CPU accepted packet %s\n", pkt->print());
    }
    return succ;
  }

  void CounterCache::CPUSidePort::recvFunctional(PacketPtr pkt)
  {
    // DPRINTF(CounterCacheCpp, "recvFunctional\n");
    // Just forward to the memobj.
    return owner->handleFunctional(pkt);
  }

  bool CounterCache::CPUSidePort::recvTimingReq(PacketPtr pkt)
  {
    DPRINTF(CounterCacheCpp, "➡️️recvTimingReq, pkt-> %s\n", pkt->print());
    return owner->handleRequest(pkt);
  }

  void CounterCache::CPUSidePort::recvRespRetry()
  {
    DPRINTF(CounterCacheCpp, "recvRespRetry\n");
    owner->pendingRequest = false;
    owner->cpuBlocked = false;
  }

  // PLAN TO DEPRECATE
  bool CounterCache::MemSidePort::sendPacket(PacketPtr pkt)
  {
    DPRINTF(CounterCacheCpp, "sendPacket\n");
    bool succ = sendTimingReq(pkt);
    if (!succ) // return false, retry request will come later
    {
      DPRINTF(CounterCacheCpp, "memory denied packet, entering state MEM_WAITING_RETRY\n");
      DPRINTF(CounterCacheCpp, "❌ Memory denied packet %s", pkt->print());
    }
    else
    { // succesful send
      DPRINTF(CounterCacheCpp, "✅ Memory accepted packet %s\n", pkt->print());
    }
    return succ;
  }

  // similar to regular sendpacket, references request queue instead of a single packet
  bool CounterCache::MemSidePort::sendPacketQueue()
  {
    DPRINTF(CounterCacheCpp, "sendPacketQueue\n");
    DPRINTF(CounterCacheCpp, "requestQueue.size: %d\n", owner->requestQueue.size());

    if (owner->memBlocked)
    {
      DPRINTF(CounterCacheCpp, "Memory is blocked. Need to wait for a retry before attempting\n");
      return false;
    }
    if (owner->requestQueue.empty())
    {
      DPRINTF(CounterCacheCpp, "⚠️ requestQueue is empty. nothing to send\n");
      return false;
    }

    PacketPtr pkt = std::get<0>(owner->requestQueue.front());
    bool succ = sendTimingReq(pkt);
    if (!succ) // return false, retry request will come later
    {
      DPRINTF(CounterCacheCpp, "memory denied packet, entering state MEM_WAITING_RETRY\n");
      DPRINTF(CounterCacheCpp, "❌ Memory denied packet %s", pkt->print());
      owner->memBlocked = true;
    }
    else
    { // succesful send
      owner->requestQueue.pop();
      DPRINTF(CounterCacheCpp, "✅ Memory accepted packet %s\n", pkt->print());
    }
    return succ;
  }

  bool CounterCache::MemSidePort::recvTimingResp(PacketPtr pkt)
  {
    DPRINTF(CounterCacheCpp, "⬅️ recvTimingResp\n");
    return owner->handleResponse(pkt);
  }

  void CounterCache::MemSidePort::recvReqRetry()
  {
    DPRINTF(CounterCacheCpp, "recvReqRetry\n");
    owner->pendingResponse = false;
    owner->memBlocked = false;

    sendPacketQueue();
  }

  void CounterCache::MemSidePort::recvRangeChange()
  {
    DPRINTF(CounterCacheCpp, "recvRangeChange\n");
    owner->sendRangeChange();
  }

  // secure module main methods
  void CounterCache::handleCpuReqRetry()
  {
    if (pendingRequest)
    {
      DPRINTF(CounterCacheCpp, "Sending CPU request retry\n");
      pendingRequest = false;
      cpuPort.sendRetryReq();
      return;
    }
  }

  void CounterCache::handleMemRespRetry()
  {
    if (pendingResponse)
    {
      DPRINTF(CounterCacheCpp, "Sending MEM response retry\n");
      pendingResponse = false;
      memPort.sendRetryResp();
      return;
    }
  }

  bool CounterCache::handleRequest(PacketPtr pkt)
  {
    DPRINTF(CounterCache, "%s for addr %#x\n", pkt->cmdString(), pkt->getAddr());
    DPRINTF(CounterCacheCpp, "handleRequest . pkt-type: %s for addr %#x\n", pkt->cmdString(), pkt->getAddr());

    bool *b = new bool(false);
    std::tuple<PacketPtr, bool *> p = std::make_tuple(pkt, b);
    bool succ = requestQueue.push(p);
    if (!succ)
    {
      DPRINTF(CounterCacheCpp, "enqueueRequest failed\n");
      pendingRequest = true;
    }
    else
    {
      pendingRequest = false; // by virtue of the queue having space
      DPRINTF(CounterCacheCpp, "enqueueRequest success\n");
      // add to the event queue to process a request from the queue

      Tick read_delay = clockEdge(mem_issue_latency + read_issue_latency + static_cast<Cycles>(1));
      Tick write_delay = clockEdge(mem_issue_latency + write_issue_latency + static_cast<Cycles>(1));

      if (pkt->cmdString().find("Read"))
      {
        stats.readReqs++;
        DPRINTF(CounterCacheCpp, "Read req: scheduling for tick %d\n", read_delay);
        schedule(new EventFunctionWrapper([this, b]
                                          { setPacketReady(b); },
                                          name() + ".accessEvent", true),
                 read_delay); // TODO: update this hardcoded value to a param
      }
      else if (pkt->cmdString().find("Write"))
      {
        stats.writeReqs++;
        DPRINTF(CounterCacheCpp, "Write req: scheduling for tick %d\n", write_delay);
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

  bool CounterCache::handleResponse(PacketPtr pkt)
  {
    DPRINTF(CounterCache, "Got response for addr %#x\n", pkt->getAddr());
    DPRINTF(CounterCacheCpp, "handleResponse. pkt-type: %s\n", pkt->cmdString());

    // we got here because memPort.recvTimingResp was called.
    // either we succesfully add pkt to respons queue or we return false to sender
    // and ask for a retry later when we're ready
    bool succ = responseQueue.push(pkt);
    if (!succ)
    {
      DPRINTF(CounterCacheCpp, "enqueueResponse failed\n");
      pendingResponse = true;
    }
    else
    {
      pendingResponse = false; // by virtue of the queue having space
      DPRINTF(CounterCacheCpp, "enqueueResponse success\n");
    }
    return succ;
  }

  void CounterCache::setPacketReady(bool *b)
  {
    // simple function that sets a flag to true
    DPRINTF(CounterCacheCpp, "setPacketReady\n");
    *b = true;
  }

  void CounterCache::cleanReady()
  {
    DPRINTF(CounterCacheCpp, "cleanReady\n");
    // should not execute here if we are not in the ready state
    if (cpuWaiting)
    {
      DPRINTF(CounterCacheCpp, "sendingRetyReq\n");
      cpuPort.sendRetryReq();
    }
  }

  void CounterCache::handleFunctional(PacketPtr pkt)
  {
    // DPRINTF(CounterCacheCpp, "handleFunctional\n");
    // Just pass this on to the memory side to handle for now.
    memPort.sendFunctional(pkt);
  }

  AddrRangeList CounterCache::getAddrRanges() const
  {
    DPRINTF(CounterCacheCpp, "getAddrRanges\n");
    DPRINTF(CounterCache, "Sending new ranges\n");
    // Just use the same ranges as whatever is on the memory side.
    return memPort.getAddrRanges();
  }

  void CounterCache::sendRangeChange()
  {
    DPRINTF(CounterCacheCpp, "sendRangeChange\n");
    cpuPort.sendRangeChange();
  }
  // atomics
  Tick CounterCache::CPUSidePort::recvAtomic(PacketPtr pkt)
  {
    DPRINTF(CounterCacheCpp, "recvAtomic\n");
    Tick tick = owner->memPort.sendAtomic(pkt);
    return tick;
  }

  CounterCache::CounterCacheStats::CounterCacheStats(statistics::Group *parent)
      : statistics::Group(parent),
        ADD_STAT(readReqs, statistics::units::Count::get(), "Number of read requests"),
        ADD_STAT(writeReqs, statistics::units::Count::get(), "Number of write requests")
  {
    // do nothing
  }

} // namespace gem5
