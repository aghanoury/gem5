#ifndef __MEM_PIPE_HH__
#define __MEM_PIPE_HH__

#include "mem/port.hh"
#include "params/MemPipe.hh"
#include "sim/clocked_object.hh"

// super boiler plate class that just forwards traffic between cpu/mem ports with no added delay
// only being used now for printing packets for trace collection
namespace gem5
{

  class MemPipe : public ClockedObject
  {
  private:
    // ports
    class CPUSidePort : public ResponsePort
    {
    private:
      /// The object that owns this object (SimpleMemobj)
      MemPipe *owner;

      /// True if the port needs to send a retry req.
      // with edits)
      bool needRetry;

      PacketPtr blockedPacket;

    public:
      /**
       * Constructor. Just calls the superclass constructor.
       */
      CPUSidePort(const std::string &name, MemPipe *owner)
          : ResponsePort(name), owner(owner), needRetry(false),
            blockedPacket(nullptr) {}

      /**
       * Send a packet across this port. This is called by the owner and
       * all of the flow control is hanled in this function.
       *
       * @param packet to send.
       */
      bool sendPacket(PacketPtr pkt);

      bool sendPacketQueue();

      /**
       * Get a list of the non-overlapping address ranges the owner is
       * responsible for. All response ports must override this function
       * and return a populated list with at least one item.
       *
       * @return a list of ranges responded to
       */
      AddrRangeList getAddrRanges() const override;

      /**
       * Send a retry to the peer port only if it is needed. This is called
       * from the SimpleMemobj whenever it is unblocked.
       */
      void trySendRetry();

    protected:
      /**
       * Receive an atomic request packet from the request port.
       * No need to implement in this simple memobj.
       */
      Tick recvAtomic(PacketPtr pkt) override;

      /**
       * Receive a functional request packet from the request port.
       * Performs a "debug" access updating/reading the data in place.
       *
       * @param packet the requestor sent.
       */
      void recvFunctional(PacketPtr pkt) override;

      /**
       * Receive a timing request from the request port.
       *
       * @param the packet that the requestor sent
       * @return whether this object can consume the packet. If false, we
       *         will call sendRetry() when we can try to receive this
       *         request again.
       */
      bool recvTimingReq(PacketPtr pkt) override;

      /**
       * Called by the request port if sendTimingResp was called on this
       * response port (causing recvTimingResp to be called on the request
       * port) and was unsuccesful.
       */
      void recvRespRetry() override;
    };

    class MemSidePort : public RequestPort
    {
    private:
      /// The object that owns this object (SimpleMemobj)
      MemPipe *owner;

      /// If we tried to send a packet and it was blocked, store it here
      PacketPtr blockedPacket;

    public:
      /**
       * Constructor. Just calls the superclass constructor.
       */
      MemSidePort(const std::string &name, MemPipe *owner)
          : RequestPort(name), owner(owner), blockedPacket(nullptr) {}

      /**
       * Send a packet across this port. This is called by the owner and
       * all of the flow control is hanled in this function.
       *
       * @param packet to send.
       */
      bool sendPacket(PacketPtr pkt);

      bool sendPacketQueue();

    protected:
      /**
       * Receive a timing response from the response port.
       */
      bool recvTimingResp(PacketPtr pkt) override;

      /**
       * Called by the response port if sendTimingReq was called on this
       * request port (causing recvTimingReq to be called on the responder
       * port) and was unsuccesful.
       */
      void recvReqRetry() override;

      /**
       * Called to receive an address range change from the peer responder
       * port. The default implementation ignores the change and does
       * nothing. Override this function in a derived class if the owner
       * needs to be aware of the address ranges, e.g. in an
       * interconnect component like a bus.
       */
      void recvRangeChange() override;

      // void sendRetryResp() override;
    };

    /**
     * Handle a packet functionally. Update the data on a write and get the
     * data on a read.
     *
     * @param packet to functionally handle
     */
    void handleFunctional(PacketPtr pkt);

    /**
     * Return the address ranges this memobj is responsible for. Just use the
     * same as the next upper level of the hierarchy.
     *
     * @return the address ranges this memobj is responsible for
     */
    AddrRangeList getAddrRanges() const;

    /**
     * Tell the CPU side to ask for our memory ranges.
     */
    void sendRangeChange();

    // ports
    CPUSidePort cpuPort;
    MemSidePort memPort;

    // Other MemPipe stuff
  public:
    MemPipe(const MemPipeParams &p);

    void startup() override;

    /**
     * Get a port with a given name and index. This is used at
     * binding time and returns a reference to a protocol-agnostic
     * port.
     *
     * @param if_name Port name
     * @param idx Index in the case of a VectorPort
     *
     * @return A reference to the given port
     */
    Port &getPort(const std::string &if_name,
                  PortID idx = InvalidPortID) override;
  };

} // namespace gem5

#endif // __SECURE_MODULE_HH__
