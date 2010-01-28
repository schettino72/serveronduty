import time
import signal

if __name__ == '__main__':

    def handler(signum, frame):
        print 'Signal handler called with signal', signum

    signal.signal(signal.SIGTERM, handler)

    while True:
        print "hehe"
        time.sleep(1)

