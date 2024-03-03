#include "rowhammer/chlink/ch_link.hh"

#include <iostream>

#include "base/trace.hh"
#include "debug/ChLink.hh"
#include "debug/ChLinkCpp.hh"

namespace gem5
{

  ChLink::ChLink(const ChLinkParams &params)
      : ClockedObject(params), waitingPortId(-1),
        cpuPort(params.name + ".cpu_side", this),
        memPort(params.name + ".mem_side", this), latency(params.latency),
        blocked(false) {}

  // unimplemented, nothing needs to be done here
  void ChLink::startup() {}

  // TODO: can we use this same one for both cpu and mem side ports?
  Port &ChLink::getPort(const std::string &if_name, PortID idx)
  {
    DPRINTF(ChLinkCpp, "ChLink: getPort %s\n", if_name);

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
      return ClockedObject::getPort(if_name, idx);
    }
  }

  bool ChLink::CPUSidePort::sendPacket(PacketPtr pkt)
  {
    DPRINTF(ChLinkCpp, "Sending packet: %s\n", pkt->print());

    // If we can't send the packet across the port, store it for later.
    // TODO: do we even need this?
    return sendTimingResp(pkt);
  }
  AddrRangeList ChLink::CPUSidePort::getAddrRanges() const
  {
    DPRINTF(ChLinkCpp, "ChLink: getAddrRanges\n");
    return owner->getAddrRanges();
  }

  void ChLink::CPUSidePort::trySendRetry()
  {
    DPRINTF(ChLinkCpp, "ChLink: trySendRetry\n");
    if (needRetry && blockedPacket == nullptr)
    {
      // Only send a retry if the port is now completely free
      needRetry = false;
      DPRINTF(ChLink, "Sending retry req for %d\n", id);
      sendRetryReq();
    }
  }

  void ChLink::CPUSidePort::recvFunctional(PacketPtr pkt)
  {
    DPRINTF(ChLinkCpp, "ChLink: recvFunctional\n");
    // Just forward to the memobj.
    return owner->handleFunctional(pkt);
  }

  bool ChLink::CPUSidePort::recvTimingReq(PacketPtr pkt)
  {
    DPRINTF(ChLinkCpp, "ChLink: recvTimingReq, pkt-> %s\n", pkt->print());

    // TODO: do we need this catch anymore?
    // if (blockedPacket || needRetry) {
    //   // The cache may not be able to send a reply if this is blocked
    //   DPRINTF(ChLinkCpp, "Request blocked\n");
    //   needRetry = true;
    //   return false;
    // }
    // Just forward to the cache.
    bool status = owner->handleRequest(pkt);
    return status;
  }

  void ChLink::CPUSidePort::recvRespRetry()
  {
    DPRINTF(ChLinkCpp, "ChLink: recvRespRetry\n");
    // We should have a blocked packet if this function is called.
    assert(blockedPacket != nullptr);

    // Grab the blocked packet.
    PacketPtr pkt = blockedPacket;
    blockedPacket = nullptr;

    // Try to resend it. It's possible that it fails again.
    sendPacket(pkt);
  }

  bool ChLink::MemSidePort::sendPacket(PacketPtr pkt)
  {
    DPRINTF(ChLinkCpp, "ChLink: sendPacket\n");
    // Note: This flow control is very simple since the memobj is blocking.
    return sendTimingReq(pkt);
  }

  bool ChLink::MemSidePort::recvTimingResp(PacketPtr pkt)
  {
    DPRINTF(ChLinkCpp, "ChLink: recvTimingResp\n");
    // Just forward to the memobj.
    return owner->handleResponse(pkt);
  }

  void ChLink::MemSidePort::recvReqRetry()
  {
    DPRINTF(ChLinkCpp, "ChLink: recvReqRetry\n");
    // We should have a blocked packet if this function is called.
    // assert(blockedPacket != nullptr);

    // // Grab the blocked packet.
    PacketPtr pkt = blockedPacket;
    blockedPacket = nullptr;
    fatal("should not get here?");

    // Try to resend it. It's possible that it fails again.
    sendPacket(pkt);
  }

  void ChLink::MemSidePort::recvRangeChange()
  {
    DPRINTF(ChLinkCpp, "ChLink: recvRangeChange\n");
    owner->sendRangeChange();
  }

  // handle packet requests
  bool ChLink::handleRequest(PacketPtr pkt)
  {
    DPRINTF(ChLink, "Got request for addr %#x\n", pkt->getAddr());
    DPRINTF(ChLinkCpp, "ChLink: handleRequest. pkt: %s\n", pkt->print());
    // if (blocked) {
    //   // There is currently an outstanding request. Stall.
    //   return false;
    // }
    // assert(waitingPortId == -1);
    // waitingPortId = port_id;

    // This memobj is now blocked waiting for the response to this packet.
    // Simply forward to the memory port

    // case should happen
    // memPort.sendPacket(pkt); // <-- old method, this works
    schedule(new EventFunctionWrapper([this, pkt]
                                      { memPort.sendPacket(pkt); },
                                      name() + ".accessEvent", true),
             clockEdge(latency));

    return true;
  }

  bool ChLink::handleResponse(PacketPtr pkt)
  {
    DPRINTF(ChLinkCpp, "ChLink: handleResponse\n");
    // assert(blocked);

    // The packet is now done. We're about to put it in the port, no need for
    // this object to continue to stall.
    // We need to free the resource before sending the packet in case the CPU
    // tries to send another request immediately (e.g., in the same callchain).
    Addr packet_addr = pkt->getAddr();
    DPRINTF(ChLink, "Got response for addr %#x\n", packet_addr);
    blocked = false;

    // int port = waitingPortId;
    // waitingPortId = -1;

    // schedule(new EventFunctionWrapper(
    //              [this, port, pkt] { cpuPorts[port].sendPacket(pkt); },
    //              name() + ".accessEvent", true),
    //          clockEdge(latency));
    schedule(new EventFunctionWrapper([this, pkt]
                                      { cpuPort.sendPacket(pkt); },
                                      name() + ".accessEvent", true),
             clockEdge(latency));

    return true;
  }

  void ChLink::handleFunctional(PacketPtr pkt)
  {
    DPRINTF(ChLinkCpp, "ChLink: handleFunctional\n");
    // Just pass this on to the memory side to handle for now.
    memPort.sendFunctional(pkt);
  }

  AddrRangeList ChLink::getAddrRanges() const
  {
    DPRINTF(ChLinkCpp, "ChLink: getAddrRanges\n");
    DPRINTF(ChLink, "Sending new ranges\n");
    // Just use the same ranges as whatever is on the memory side.
    return memPort.getAddrRanges();
  }

  void ChLink::sendRangeChange()
  {
    DPRINTF(ChLinkCpp, "ChLink: sendRangeChange\n");
    cpuPort.sendRangeChange();
    // for (auto &port : cpuPorts) {
    //   port.sendRangeChange();
    // }
  }

} // namespace gem5
