import random, string, sys

import os

def getMemory():
        # returns memory utilization in MB
        f = open("/proc/%s/status" % (os.getpid(),), "r")
        vmsize = None
        vmrss = None
        for l in f.readlines():
            l = l.strip()
            if l.startswith("VmSize:"):
                vmsize = int(l.split()[1])
            elif l.startswith("VmRSS:"):
                vmrss = int(l.split()[1])
        return float(vmsize)/1024.0, float(vmrss)/1024.0

alphabet = string.ascii_letters + string.digits + "/"

def random_name(l):
	return "/" + "".join(random.choices(alphabet, k=l-1))


class FrameReader(object):
	def __init__(self, f):
		self.F = f
		self.EOF = False

	def rewind(self):
		self.F.seek(0)
		self.EOF = False

	def frame(self, n):
		out = set()
		while n > 0:
			l = self.F.readline()
			if not l:	
				self.EOF = True
				break
			out.add(l)
			n -= 1
		return out

	def frames(self, n):
		while not self.EOF:
			yield self.frame(n)

def diff(x, y, frame_size):
	x_minus_y = set()
	x.rewind()
	ix = 0
	for x_frame in x.frames(frame_size):
		y.rewind()
		iy = 0
		for y_frame in y.frames(frame_size):
			x_frame -= y_frame
			iy += 1
		x_minus_y |= x_frame
		ix += 1
	return x_minus_y

def cmp3_frames(a, r, b, frame_size):
	#
	# produces 2 lists:
	#
	# 	D = R-A-B = (R-A)-B
	# 	M = A*B-R = (A-R)*B
	#
	a_r = diff(a, r, frame_size)
	print("A-R:", len(a_r))
	r_a = diff(r, a, frame_size)
	print("R-A:", len(r_a))

	d = r_a
	m = set()
	for b_frame in b.frames(frame_size):
		d -= b_frame
		m |= b_frame & a_r
	print("memory utilization at the end of cmp3, MB:", getMemory())
	return list(d), list(m)

def gen3(n, r):
	# generates 3 almost identical lists. r controls the "errors"

	for _ in range(n):
		x = random_name(100)
		yield tuple(None if r > random.random() else x for _ in (0,0,0))

def main():
	if sys.argv[1] == "gen":
		n = int(sys.argv[2])
		fa = open("/tmp/a.list", "w")
		fr = open("/tmp/r.list", "w")
		fb = open("/tmp/b.list", "w")
		for a, r, b in gen3(n, 0.01):
			if a:	fa.write(a + "\n")
			if b:	fb.write(b + "\n")
			if r:	fr.write(r + "\n")
		fa.close()
		fb.close()
		fr.close()

	elif sys.argv[1] == "cmp":
		fa = FrameReader(open("/tmp/a.list", "r"))
		fr = FrameReader(open("/tmp/r.list", "r"))
		fb = FrameReader(open("/tmp/b.list", "r"))

		d, m = cmp3_frames(fa, fr, fb, 5000000)
		d, m = sorted(d), sorted(m)
		print("Dark:   ", len(d))
		print("Missing:", len(m))
		fd = open("/tmp/d.list","w")
		fm = open("/tmp/m.list","w")
		for x in d:
			fd.write(x)			# training newlines are there already
		for x in m:
			fm.write(x)
		fd.close()
		fm.close()

		

		



if __name__ == "__main__":
	main()
		

