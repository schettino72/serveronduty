import time
import sys

def main(num_sleep):
    for i in range(num_sleep):
        time.sleep(1)
    print "done"

if __name__ == "__main__":
    main(int(sys.argv[1]))
