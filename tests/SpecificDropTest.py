from BasicTest import *
import random

"""
This tests random packet drops. We randomly decide to drop about half of the
packets that go through the forwarder in either direction.

Note that to implement this we just needed to override the handle_packet()
method -- this gives you an example of how to extend the basic test case to
create your own.
"""
class SpecificDropTest(BasicTest):
    def handle_packet(self):
        for p in self.forwarder.in_queue:
            seqno = message.split('|')[1]
            if not seqno == 3:
                self.forwarder.out_queue.append(p)
                print(seqno)
            else:
                print("dropped packet: " + str(p))

        # empty out the in_queue
        self.forwarder.in_queue = []

    def split_message(self, message): #we receive start|<sequence number>|<data>|<checksum>
        pieces = message.split('|')
        msg_type, seqno = pieces[0:2]  #First 2 are ack and seqno; checksum is alr checked -> leave it
        return seqno
