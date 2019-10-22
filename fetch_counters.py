#!/usr/bin/python3

# Run with PYTHONPATH=`dirname \`find . -name renderdoc.so\``

import argparse
import sys
import renderdoc

# Alias renderdoc for legibility
rd = renderdoc

draws = {}

# Define a recursive function for iterating over draws
def iterDraw(d, indent = ''):
        global draws

        # save the drawcall by eventId
        draws[d.eventId] = d

        # Iterate over the draw's children
        for d in d.children:
                iterDraw(d, indent + '    ')

def sampleCode(controller, output):
        # Iterate over all of the root drawcalls, so we have names for each
        # eventId
        for d in controller.GetDrawcalls():
                iterDraw(d)

        # Enumerate the available counters
        counters = { c : controller.DescribeCounter(c) for c in controller.EnumerateCounters() }

        # Filter by name if needed
        counters = { c : d for (c, d) in counters.items() if 'Samples' in d.name }

        # Describe each counter
        for c in counters.values():
                print("Counter %d (%s): %s" % (c.counter, c.name, c.description))

        # Now we fetch the counter data, this is a good time to batch requests of as many
        # counters as possible, the implementation handles any book keeping.
        results = controller.FetchCounters([c for c in counters])

        # Print the header for the csv columns.
        first_line = "EventId"
        for c in sorted([c for c in counters.keys()]):
                first_line += ", %s (%s)" % (counters[c].name, counters[c].unit)
        output.write(first_line + "\n")

        # For each draw call, print the counter values.
        for d in draws.keys():
                draw = draws[d]

                # Only care about draws, not about clears and other misc events
                if not (draw.flags & rd.DrawFlags.Drawcall):
                        continue

                draw_results = sorted(filter(lambda r: r.eventId == draw.eventId, results), key=lambda r: r.counter)

                line = "%u" % draw.eventId
                for r in draw_results:
                        desc = counters[r.counter]

                        if desc.resultType == rd.CompType.Float:
                                line += ", %f" % r.value.f
                        elif desc.resultType in (rd.CompType.UInt,
                                                 rd.CompType.SInt,
                                                 rd.CompType.UNorm,
                                                 rd.CompType.UScaled,
                                                 rd.CompType.SNorm,
                                                 rd.CompType.SScaled):
                                if desc.resultByteWidth == 4:
                                        line += ", %u" % r.value.u32
                                else:
                                        line += ", %u" % r.value.u64
                output.write(line + "\n")

def loadCapture(filename):
        # Open a capture file handle
        cap = rd.OpenCaptureFile()

        # Open a particular file - see also OpenBuffer to load from memory
        status = cap.OpenFile(filename, '', None)

        # Make sure the file opened successfully
        if status != rd.ReplayStatus.Succeeded:
                raise RuntimeError("Couldn't open file: " + str(status))

        # Make sure we can replay
        if not cap.LocalReplaySupport():
                raise RuntimeError("Capture cannot be replayed")

        # Initialise the replay
        status,controller = cap.OpenCapture(rd.ReplayOptions(), None)

        if status != rd.ReplayStatus.Succeeded:
                raise RuntimeError("Couldn't initialise replay: " + str(status))

        return cap,controller

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rdc', help='Renderdoc file to extract performance counters from', required=True)
    parser.add_argument('--output', help='Output csv file', required=True)
    args = parser.parse_args()

    cap,controller = loadCapture(args.rdc)

    with open(args.output, 'w') as f:
            sampleCode(controller, f)

    controller.Shutdown()
    cap.Shutdown()

if __name__ == '__main__':
    main()
