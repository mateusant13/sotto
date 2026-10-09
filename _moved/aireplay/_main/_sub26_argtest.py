import sys
print("ARGC=%d" % len(sys.argv))
for i,a in enumerate(sys.argv): print("  argv[%d]=%r" % (i,a))
