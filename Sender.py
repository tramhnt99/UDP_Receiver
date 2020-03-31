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
        self.debug = False
        self.currAckSeqno = 0
        self.lastSentSeqno = 0
        self.max_buf_size = 5
        self.timeout = 10 #time.time() returns flatings
        self.seq_acks = {} #hashing acks
        self.updated = time.time()
        if sackMode:
            raise NotImplementedError  # remove this line when you implement SACK
        if filename is None:
            self.infile = sys.stdin
        else:
            self.infile = open(filename, "r")

    #implement a time_out at init

    #handle_response must:
        #check the Checksum
        #Ack -> check the sequence number -> ...

    def handle_response(self, response_packet):
        if not Checksum.validate_checksum(response_packet):
            print("recv: %s <--- CHECKSUM FAILED" % response_packet)
            return #drop the packet
        else:
            print("recv: %s" % response_packet)

            #check for time out
            if time.time() - self.updated > self.timeout:
                print("Sender.py packet timed out")
                self.handle_timeout()
            else:
                self.updated = time.time()
                msg_type, seqno = self.split_message(response_packet)

                #check if is in window, else we drop the packet

                # print(seqno)
                # print(self.currAckSeqno + self.max_buf_size)
                # print(seqno < self.currAckSeqno + self.max_buf_size)

                #THIS IS EVALUATING INCORRECT ->   and seqno <= self.currAckSeqno + self.max_buf_size
                #ok, assuming we won't be receiving acks beyond our window
                if seqno > self.currAckSeqno:
                    if msg_type == 'ack':
                        if seqno in self.seq_acks:
                            self.handle_dup_ack(response_packet)
                        else:
                            self.seq_acks[seqno] = msg_type #store something arbitrary
                            self.handle_new_ack(response_packet)

    #TODO: implement window
    #TODO: to implement timeout -> we need an array for each packet we've sent (at most 5) to keep track
    #TODO: rewrite the start -> only handles sending the 'start'
    #   handle functions handle the sending/resending of packets
    def start(self):
        msg = self.infile.read(500)
        msg_type = None
        while not msg_type == 'end':
            next_msg = self.infile.read(500)

            msg_type = 'data'
            if self.currAckSeqno == 0:
                msg_type = 'start' #starting the connection
            elif next_msg == "":
                msg_type = 'end' #ending the connection

            packet = self.make_packet(msg_type, self.currAckSeqno, msg)
            self.send(packet)
            # print "sent: %s" % packet

            response = self.receive()
            self.handle_response(response)

            msg = next_msg
            self.currAckSeqno += 1

        self.infile.close()


    def handle_timeout(self):
        pass

    def handle_new_ack(self, ack):
        for n in sorted(self.seq_acks.keys()):
            if n == str(self.currAckSeqno + 1):
                del self.seq_acks[n]
                print("self.seq_acks is " + str(self.seq_acks))
            else:
                break #CONTINUE HERE: double check the corner case of when this first starts
                        #check for when acks are recieved not in order

    def handle_dup_ack(self, ack):
        pass

    def log(self, msg):
        if self.debug:
            print msg

    def split_message(self, message): #we receive ack|<seqno>|<checksum|
        pieces = message.split('|')
        msg_type, seqno = pieces[0:2]  #First 2 are ack and seqno; checksum is alr checked -> leave it
        return msg_type, seqno


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
