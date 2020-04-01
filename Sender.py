import sys
import getopt
import time

import Checksum
import BasicSender

'''
This is a skeleton sender class. Create a fantastic transport protocol here.
'''


class Sender(BasicSender.BasicSender):
    def __init__(self, dest, port, filename, debug=False, sackMode=False):
        super(Sender, self).__init__(dest, port, filename, debug)
        if filename is None:
            self.infile = sys.stdin
        else:
            self.infile = open(filename, "r")
        self.debug = False
        self.currAckSeqno = 0
        self.toSendSeqno = 0
        self.max_buf_size = 5
        self.timeout = 10 #time.time() returns flatings
        self.seq_acks = {} #hashing acks
        self.seq_msgs = {} #hashing sent messages
        self.next_msg = self.infile.read(500)
        self.msg_type = 'start'
        self.retrans = False
        if sackMode:
            raise NotImplementedError  # remove this line when you implement SACK

    def handle_response(self, response_packet):
        if not Checksum.validate_checksum(response_packet):
            print("recv: %s <--- CHECKSUM FAILED" % response_packet)
            return #drop the packet
        else:
            print("recv: %s" % response_packet)
            msg_type, seqno = self.split_message(response_packet)

            if seqno > self.currAckSeqno: #assuming we won't receive seqno beyond our window
                if msg_type == 'ack':
                    if seqno in self.seq_acks:
                        self.seq_acks[seqno] += 1
                        self.handle_dup_ack(response_packet)
                    else:
                        self.seq_acks[seqno] = 1 #store number of dupls
                        self.handle_new_ack(response_packet)


    #TODO: implement window
    #TODO: to implement timeout -> we need an array for each packet we've sent (at most 5) to keep track
    #TODO: rewrite the start -> only handles sending the 'start' and receiving
    #   handle functions handle the sending/resending of packets
    def start(self):

        assert self.msg_type == 'start'
        packet = self.make_packet(self.msg_type, self.toSendSeqno, self.next_msg)
        self.send(packet)
        print("sent packet: " + str(self.toSendSeqno))
        self.seq_msgs[self.toSendSeqno] = self.next_msg
        self.toSendSeqno += 1

        #send the next 4 packets
        self.msg_type = 'data'
        for i  in range(4):
            self.next_msg = self.infile.read(500)
            if self.next_msg == "":
                self.msg_type = 'end'
            packet = self.make_packet(self.msg_type, self.toSendSeqno, self.next_msg)

            #just for Testing
            if not self.toSendSeqno == 3:
                self.send(packet)

            self.seq_msgs[self.toSendSeqno] = self.next_msg
            print("sent packet: " + str(self.toSendSeqno))
            self.toSendSeqno += 1
            if self.msg_type == 'end':
                break


        while self.currAckSeqno < self.toSendSeqno:

            response = self.receive()
            self.handle_response(response)

        self.infile.close()



    def handle_new_ack(self, ack):

        msg_type, seqno = self.split_message(ack) #note seqno = no. of packet sent + 1

        if self.retrans == True:
            self.currAckSeqno = int(seqno) - 1

            #removed previously acked msgs
            for i in self.seq_msgs.keys():
                if i < self.currAckSeqno:
                    del self.seq_msgs[i]
            self.retrans = False

        for n in sorted(self.seq_acks.keys()):
            if n == str(self.currAckSeqno + 1):
                # print(n)
                del self.seq_acks[n]
                del self.seq_msgs[self.currAckSeqno]
                self.currAckSeqno += 1
                # print("self.currAckSeqno: " + str(self.currAckSeqno))

                #sending more packets
                if self.msg_type == 'end': #we've sent all packets - now we just wait for all acks
                    return
                else:
                    if self.toSendSeqno <= self.currAckSeqno + self.max_buf_size:

                        #send all packets we can send in a window
                        for i in range(self.toSendSeqno, self.currAckSeqno + self.max_buf_size):
                            self.next_msg = self.infile.read(500)
                            self.msg_type = 'data'
                            if self.next_msg == "":
                                self.msg_type = 'end'

                            packet = self.make_packet(self.msg_type, self.toSendSeqno, self.next_msg)
                            self.send(packet)
                            print("sent packet: " + str(self.toSendSeqno))
                            self.seq_msgs[self.toSendSeqno] = self.next_msg
                            msg = self.next_msg
                            # print(self.utf8len(msg))
                            self.toSendSeqno += 1
                            
                            if self.msg_type == 'end':
                                break
            else:
                break

    def handle_dup_ack(self, ack):
        msg_type, seqno = self.split_message(ack) #note seqno = no. of packet sent + 1
        if self.seq_acks[seqno] == self.max_buf_size - 1: #retransmit after getting 4 dups
            self.retrans = True
            del self.seq_acks[seqno]
            for i in range(self.currAckSeqno, self.currAckSeqno + self.max_buf_size):

                #resending the window
                #if the packet has been sent and recorded
                if i in self.seq_msgs:
                    packet = self.make_packet(self.msg_type, i, self.seq_msgs[i])
                    self.send(packet)
                    print("Resent packet " + str(i))



    def handle_timeout(self):
        pass

    def log(self, msg):
        if self.debug:
            print(msg)

    def split_message(self, message): #we receive ack|<seqno>|<checksum|
        pieces = message.split('|')
        msg_type, seqno = pieces[0:2]  #First 2 are ack and seqno; checksum is alr checked -> leave it
        return msg_type, seqno

    def utf8len(self, s):
        return len(s.encode('utf-8'))


'''
This will be run if you run this script from the command line. You should not
change any of this; the grader may rely on the behavior here to test your
submission.
'''
if __name__ == "__main__":
    def usage():
        print "BULLDOGS-TP Sender"
        print "-f FILE | --file=FILE The file to transfer; if empty reads from STDIN"
        print "-p PORT | --port=PORT The destination port, defaults to 33122"
        print "-a ADDRESS | --address=ADDRESS The receiver address or hostname, defaults to localhost"
        print "-d | --debug Print debug messages"
        print "-h | --help Print this usage message"
        print "-k | --sack Enable selective acknowledgement mode"


    try:
        opts, args = getopt.getopt(sys.argv[1:],
                                   "f:p:a:dk", ["file=", "port=", "address=", "debug=", "sack="])
    except:
        usage()
        exit()

    port = 33122
    dest = "localhost"
    filename = None
    debug = False
    sackMode = False

    for o, a in opts:
        if o in ("-f", "--file="):
            filename = a
        elif o in ("-p", "--port="):
            port = int(a)
        elif o in ("-a", "--address="):
            dest = a
        elif o in ("-d", "--debug="):
            debug = True
        elif o in ("-k", "--sack="):
            sackMode = True

    s = Sender(dest, port, filename, debug, sackMode)
    try:
        s.start()
    except (KeyboardInterrupt, SystemExit):
        exit()


            # #check for time out
            # if time.time() - self.updated > self.timeout:
            #     print("Sender.py packet timed out")
            #     self.handle_timeout()
            # else:
