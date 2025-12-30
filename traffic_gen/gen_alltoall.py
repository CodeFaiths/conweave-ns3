import sys
import random
import math
import heapq
from optparse import OptionParser

class Flow:
    def __init__(self, src, dst, size, t):
        self.src, self.dst, self.size, self.t = src, dst, size, t
    def __str__(self):
        return "%d %d 3 %d %.9f"%(self.src, self.dst, self.size, self.t)

def translate_bandwidth(b):
    if b == None:
        return None
    if type(b)!=str:
        return None
    if b[-1] == 'G':
        return float(b[:-1])*1e9
    if b[-1] == 'M':
        return float(b[:-1])*1e6
    if b[-1] == 'K':
        return float(b[:-1])*1e3
    return float(b)

def poisson(lam):
    return -math.log(1-random.random())*lam

def generate_alltoall_flows(nhost, data_size, base_t, phase_gap):
    flows = []
    
    for src in range(nhost):
        for dst in range(nhost):
            if src != dst:
                flows.append(Flow(src, dst, data_size, base_t/1e9))
    
    # for i, flow in enumerate(flows):
    #     flow.t += (i % nhost) * 1000  # offset

    return flows

def generate_chunked_alltoall_flows(nhost, data_size, base_t, phase_gap, chunks_per_flow=1):
    flows = []
    chunk_size = data_size // chunks_per_flow
    
    for src in range(nhost):
        for dst in range(nhost):
            if src != dst: 
                for chunk_idx in range(chunks_per_flow):
                    chunk_t = base_t + chunk_idx * phase_gap
                    flows.append(Flow(src, dst, chunk_size, chunk_t/1e9))
    
    return flows

if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("-n", "--nhost", dest = "nhost", help = "number of hosts")
    parser.add_option("-s", "--size", dest = "data_size", help = "total data size per flow (bytes)", default = "1048576")  # 1MB by default
    parser.add_option("-b", "--bandwidth", dest = "bandwidth", help = "the bandwidth of host link (G/M/K), by default 10G", default = "10G")
    parser.add_option("-t", "--time", dest = "time", help = "the total run time (s), by default 10", default = "10")
    parser.add_option("-o", "--output", dest = "output", help = "the output file", default = "alltoall_traffic.txt")
    parser.add_option("-a", "--algorithm", dest = "algorithm", help = "alltoall algorithm: 'basic' or 'chunked'", default = "basic")
    parser.add_option("-g", "--gaps", dest = "gaps", help = "number of alltoall operations to generate", default = "1")
    parser.add_option("-p", "--phase-gap", dest = "phase_gap", help = "time gap between chunks (ns)", default = "1000000")  # 1ms by default
    parser.add_option("-c", "--chunks", dest = "chunks", help = "number of chunks per flow (for chunked algorithm)", default = "1")
    
    options, args = parser.parse_args()
    
    base_t = 2000000000  # 2000000000ns (2s)
    
    if not options.nhost:
        print("please use -n to enter number of hosts")
        sys.exit(0)
    
    nhost = int(options.nhost)
    data_size = int(options.data_size)
    bandwidth = translate_bandwidth(options.bandwidth)
    time = float(options.time)*1e9 
    output = options.output
    algorithm = options.algorithm.lower()
    num_gaps = int(options.gaps)
    phase_gap = int(options.phase_gap)
    chunks_per_flow = int(options.chunks)
    
    if bandwidth == None:
        print("bandwidth format incorrect")
        sys.exit(0)
    
    if algorithm not in ['basic', 'chunked']:
        print("Algorithm must be 'basic' or 'chunked'")
        sys.exit(0)
    
    alltoall_gap = time / num_gaps if num_gaps > 0 else 0
    
    all_flows = []
    
    for gap in range(num_gaps):
        current_base_t = base_t + gap * alltoall_gap
        
        if algorithm == 'basic':
            flows = generate_alltoall_flows(nhost, data_size, current_base_t, phase_gap)
        else:  # chunked
            flows = generate_chunked_alltoall_flows(nhost, data_size, current_base_t, phase_gap, chunks_per_flow)
        
        all_flows.extend(flows)
    
    all_flows.sort(key=lambda x: x.t)
    
    ofile = open(output, "w")
    ofile.write("%d\n" % len(all_flows))
    
    for flow in all_flows:
        ofile.write("%s\n" % flow)
    
    ofile.close()
    print(f"Generated {len(all_flows)} flows for {algorithm} alltoall with {nhost} hosts")
    print(f"Output written to {output}")

# python gen_alltoall.py -n 256 -a basic -s 10485760 -c 4 -o basic_alltoall.txt