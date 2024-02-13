#include "mem_pipe/src/mem_pipe.hh"

#include <iostream>

#include "base/trace.hh"
#include "debug/MemPipe.hh"
#include "debug/MemPipeCpp.hh"
#include "debug/MemPipeCycles.hh"

namespace gem5
{

  // constructor
  MemPipe::MemPipe(const MemPipeParams &params)
      : ClockedObject(params),
        cpuPort(params.name + ".cpu_side", this),
        memPort(params.name + ".mem_side", this)
  {
  }

  // unimplemented, nothing needs to be done here
  void MemPipe::startup()
  {
  }

  Port &MemPipe::getPort(const std::string &if_name, PortID idx)
  {
    DPRINTF(MemPipeCpp, "getPort %s\n", if_name);

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

  AddrRangeList MemPipe::CPUSidePort::getAddrRanges() const
  {
    DPRINTF(MemPipeCpp, "getAddrRanges\n");
    return owner->getAddrRanges();
  }

  bool MemPipe::CPUSidePort::sendPacket(PacketPtr pkt)
  {
    DPRINTF(MemPipeCpp, "Sending packet: %s\n", pkt->print());
    bool succ = sendTimingResp(pkt);
    if (succ)
    {
      DPRINTF(MemPipe, "CPU <-- MEM %s, Addr: %#x\n", pkt->print(), pkt->getAddr());
    }
    return succ;
  }

  void MemPipe::CPUSidePort::recvFunctional(PacketPtr pkt)
  {
    // DPRINTF(MemPipeCpp, "recvFunctional\n");
    return owner->handleFunctional(pkt);
  }

  bool MemPipe::CPUSidePort::recvTimingReq(PacketPtr pkt)
  {
    DPRINTF(MemPipeCpp, "➡️️recvTimingReq, pkt-> %s\n", pkt->print());
    return owner->memPort.sendPacket(pkt);
    // return owner->handleRequest(pkt);
  }

  void MemPipe::CPUSidePort::recvRespRetry()
  {
    DPRINTF(MemPipeCpp, "recvRespRetry\n");
    owner->memPort.sendRetryResp();
  }

  bool MemPipe::MemSidePort::sendPacket(PacketPtr pkt)
  {
    DPRINTF(MemPipeCpp, "sendPacket\n");
    bool succ = sendTimingReq(pkt);
    if (succ)
    {
      DPRINTF(MemPipe, "CPU --> ️ MEM %s, Addr: %#x\n", pkt->print(), pkt->getAddr());
    }
    return succ;
  }

  // similar to regular sendpacket, references request queue instead of a single packet
  bool MemPipe::MemSidePort::recvTimingResp(PacketPtr pkt)
  {
    DPRINTF(MemPipeCpp, "⬅️ recvTimingResp\n");
    return owner->cpuPort.sendPacket(pkt);
  }

  void MemPipe::MemSidePort::recvReqRetry()
  {
    DPRINTF(MemPipeCpp, "recvReqRetry\n");
    owner->cpuPort.sendRetryReq();
  }

  void MemPipe::MemSidePort::recvRangeChange()
  {
    DPRINTF(MemPipeCpp, "recvRangeChange\n");
    owner->sendRangeChange();
  }

  void MemPipe::handleFunctional(PacketPtr pkt)
  {
    // DPRINTF(MemPipeCpp, "handleFunctional\n");
    memPort.sendFunctional(pkt);
  }

  AddrRangeList MemPipe::getAddrRanges() const
  {
    DPRINTF(MemPipeCpp, "getAddrRanges\n");
    DPRINTF(MemPipe, "Sending new ranges\n");
    // Just use the same ranges as whatever is on the memory side.
    return memPort.getAddrRanges();
  }

  void MemPipe::sendRangeChange()
  {
    DPRINTF(MemPipeCpp, "sendRangeChange\n");
    cpuPort.sendRangeChange();
  }

  // atomics
  Tick MemPipe::CPUSidePort::recvAtomic(PacketPtr pkt)
  {
    DPRINTF(MemPipeCpp, "recvAtomic\n");
    Tick tick = owner->memPort.sendAtomic(pkt);
    return tick;
  }

  // Tick MemPipe::MemSidePort::sendAtomic(Packet)

  // atomics
  // Tick recvAtomicBackdoor(PacketPtr pkt, MemBackdoorPtr &backdoor)
  // {
  //   DPRINTF(MemPipeCpp, "recvAtomicBackdoor\n");
  //   return 0;
  // }

} // namespace gem5
