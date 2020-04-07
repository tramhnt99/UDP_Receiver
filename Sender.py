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
        self.seq_acks = {} #hashing acks
        self.cum_acks = {}
        self.seq_msgs = {} #hashing sent messages (packets)
        self.next_msg = self.infile.read(300)
        self.msg_type = 'start'
        self.times = {} #hasing sending times
        self.timeout = 0.5 #0.5s
        self.debug = True

    def handle_response(self, response_packet):
        if not Checksum.validate_checksum(response_packet):
            print("recv: %s <--- CHECKSUM FAILED" % response_packet)
            return #drop the packet
        else:
            print("recv: %s" % response_packet)

            msg_type, seqno = self.split_message(response_packet)

            if msg_type == 'ack':

                if int(seqno) - 1 in self.times:
                    del self.times[int(seqno) - 1] #acks are +1 of seqno of packet sent

                if seqno > self.currAckSeqno: #assuming we won't receive seqno beyond our window
                    if seqno in self.seq_acks:
                        self.seq_acks[seqno] += 1
                        self.handle_dup_ack(response_packet)
                    else:
                        self.seq_acks[seqno] = 1 #store number of dupls
                        self.handle_new_ack(response_packet)

            #doesn't handle fast retransmit
            elif msg_type == 'sack':
                cum_ack = seqno.split(';')[0]
                if cum_ack in self.cum_acks:
                    self.cum_acks[cum_ack] += 1
                    self.handle_dup_ack(response_packet)
                else:
                    self.cum_acks[cum_ack] = 1
                    self.seq_acks[str(int(cum_ack) - 1)] = None
                    for i in self.cum_acks.keys():
                        if int(i) < int(cum_ack):
                            del self.cum_acks[i]
                    self.handle_new_sack(response_packet)



    def start(self):

        assert self.msg_type == 'start'
        packet = self.make_packet(self.msg_type, self.toSendSeqno, self.next_msg)
        self.send(packet)
        self.times[self.toSendSeqno] = time.time()
        self.seq_msgs[self.toSendSeqno] = packet

        self.toSendSeqno += 1
        #send the next 4 packets
        self.msg_type = 'data'

        for i  in range(4):
            self.next_msg = self.infile.read(300)
            if self.next_msg == "":
                self.msg_type = 'end'
            packet = self.make_packet(self.msg_type, self.toSendSeqno, self.next_msg)
            self.send(packet)

            #time and check time out of previous packets
            for i in self.times.keys():
                if time.time() - self.times[i] > self.timeout:
                    self.handle_timeout(i)

            self.times[self.toSendSeqno] = time.time()
            self.seq_msgs[self.toSendSeqno] = packet
            # print("sent packet: " + str(self.toSendSeqno))
            self.toSendSeqno += 1
            if self.msg_type == 'end':
                break


        while self.currAckSeqno < self.toSendSeqno:

            #time and check time out of previous packets
            for i in self.times.keys():
                if time.time() - self.times[i] > self.timeout:
                    self.handle_timeout(i)

            response = self.receive(timeout=0.4)
            if response != None: #None means that receive timed out
                self.handle_response(response)

            #just for ending
            if self.next_msg == "" and self.msg_type == 'end':
                packet = self.make_packet('end', self.toSendSeqno, "")
                self.send(packet)
                # print("resent the end packet")

        self.infile.close()



    def handle_new_ack(self, ack):

        msg_type, seqno = self.split_message(ack) #note seqno = no. of packet sent + 1

        #remove checking self.trans because receiver sends cumulative acks - ie. anything below
        #if it hasn't acked, it wouldn't send acks greater than it -> so always clear anything lower
        #cause it's acked
        self.currAckSeqno = int(seqno) - 1

        #removed previously acked msgs
        for i in self.seq_msgs.keys():
            if int(i) <= self.currAckSeqno:
                del self.seq_msgs[i]
                if i in self.times.keys():
                    del self.times[i]
        #removed previous acks
        for j in self.seq_acks.keys():
            if int(j) <= self.currAckSeqno:
                del self.seq_acks[j]

        # if self.debug:
        #     print(self.seq_acks.keys())
        #     print("self.currAckSeqno: " + str(self.currAckSeqno))

        for n in self.seq_acks.keys():
            if n == str(self.currAckSeqno + 1):
                self.seq_acks[n] -= 1
                if self.currAckSeqno in self.seq_msgs:
                    del self.seq_msgs[self.currAckSeqno]

                # if self.debug:
                #     print(self.seq_acks.keys())

                self.currAckSeqno += 1

                #sending more packets
                if self.msg_type == 'end': #we've sent all packets - now we just wait for all acks
                    return
                else:
                    if self.toSendSeqno <= self.currAckSeqno + self.max_buf_size:

                        #send all packets we can send in a window
                        for i in range(self.toSendSeqno, self.currAckSeqno + self.max_buf_size):
                            self.next_msg = self.infile.read(300)
                            self.msg_type = 'data'
                            if self.next_msg == "":
                                self.msg_type = 'end'

                            packet = self.make_packet(self.msg_type, self.toSendSeqno, self.next_msg)
                            self.send(packet)
                            # print("sent packet: " + str(self.msg_type) + str(self.toSendSeqno))

                            # just for Testing
                            # if not self.toSendSeqno % 4 == 0:
                            #     self.send(packet)

                            #time and check time out of previous packets
                            for i in self.times.keys():
                                if time.time() - self.times[i] > self.timeout:
                                    self.handle_timeout(i)

                            self.times[self.toSendSeqno] = time.time()
                            self.seq_msgs[self.toSendSeqno] = packet
                            msg = self.next_msg

                            # print(self.utf8len(msg))
                            self.toSendSeqno += 1

                            if self.msg_type == 'end':
                                break
            else:
                break

    def handle_dup_ack(self, ack):
        msg_type, seqno = self.split_message(ack) #note seqno = no. of packet sent + 1
        if msg_type == 'ack':
            if self.seq_acks[seqno] == self.max_buf_size - 1: #retransmit after getting 4 dups
                del self.seq_acks[seqno]

                #resend the packet lost only
                if self.currAckSeqno in self.seq_msgs:
                    # packet = self.make_packet(self.msg_type, self.currAckSeqno, self.seq_msgs[self.currAckSeqno])
                    self.send(self.seq_msgs[self.currAckSeqno])
                    self.times[self.currAckSeqno] = time.time() #reset timer
                    print("Resent packet " + str(self.currAckSeqno) + " due to DupAck")
        else: #msg_type == 'sack'
            cum_ack = seqno.split(';')[0]
            if self.cum_acks[cum_ack] == self.max_buf_size - 1:
            # if self.cum_acks[cum_ack] >= 3:
                del self.cum_acks[cum_ack]
                if self.currAckSeqno in self.seq_msgs:
                    self.send(self.seq_msgs[self.currAckSeqno])
                    self.times[self.currAckSeqno] = time.time()
                    print("Resent packet " + str(self.currAckSeqno) + " due to DupAck")



    def handle_timeout(self, seqno):
        if int(seqno) in self.seq_msgs:
            self.send(self.seq_msgs[int(seqno)])
            self.times[int(seqno)] = time.time() #restart NotImplementedError
            # if self.debug:
                # print("Timeout Resend: " + str(seqno))
                # print("Timeout Resend: " + str(self.seq_msgs[int(seqno)]))




    def handle_new_sack(self,msg):
        msg_type, acks = self.split_message(msg) #note seqno = no. of packet sent + 1
        l_acks = acks.split(';')
        cum_ack = l_acks[0]
        sacks = l_acks[1].split(',')

        self.currAckSeqno = int(cum_ack) - 1

        #removed previously acked msgs, cause cum_acks = everything before has been acked
        for i in self.seq_msgs.keys():
            if int(i) < self.currAckSeqno:
                del self.seq_msgs[i]
                if i in self.times.keys():
                    del self.times[i]
        #removed previous acks
        for j in self.seq_acks.keys():
            if int(j) < self.currAckSeqno:
                del self.seq_acks[j]

        for i in sacks:
            if not i == '':
                if i not in self.seq_acks.keys():
                    self.seq_acks[i] = None
                if int(i) in self.times.keys():
                    del self.times[int(i)]

        # if self.debug:
        #     print(self.times.keys())
        # print(self.seq_acks.keys())
        #     print(self.msg_type)
        #     print(self.seq_msgs.keys())
        #     print("self.currAckSeqno: " + str(self.currAckSeqno))
            # print("self.times: " + str(self.times.keys()))

        if self.msg_type == 'end':
            return
        else:
            for i in range(self.toSendSeqno, self.currAckSeqno + self.max_buf_size):
                self.next_msg = self.infile.read(300)
                self.msg_type = 'data'
                if self.next_msg == "":
                    self.msg_type = 'end'
                if not self.toSendSeqno in self.seq_acks and not self.toSendSeqno in self.seq_msgs: #if it has not been acked
                    packet = self.make_packet(self.msg_type, self.toSendSeqno, self.next_msg)
                    self.send(packet)

                    #just for Testing
                    # if not self.toSendSeqno == 8:
                    #     self.send(packet)
                        # print("sent packet: " + str(self.msg_type) + str(self.toSendSeqno))

                    for j in self.times.keys():
                        if time.time() - self.times[j] > self.timeout:
                            self.handle_timeout(j)

                    self.times[self.toSendSeqno] = time.time()
                    self.seq_msgs[self.toSendSeqno] = packet
                    self.toSendSeqno += 1
                    # msg = self.next_msg

                if self.msg_type == 'end':
                    break







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
