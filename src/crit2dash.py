#!/usr/bin/env python3
# Performance dashboard for the Monster symbolic execution engine.
# Copyright (c) 2021 Computational Systems Group. All Rights Reserved.

import argparse
import glob
import json
import re
import time

# Parse the command line arguments.
parser = argparse.ArgumentParser()
parser.add_argument("-o", "--output", required=True,
                    help="output file to be written in JSON format")
parser.add_argument("-s", "--source", required=True,
                    help="input directory with Criterion reports")
args = parser.parse_args()

# Load all available commits. This iterates over all paths holding a
# JSON file with commit metadata and populates a `commits` dictionary
# mapping commit ids to the full metadata.
commits = {}
for filename in glob.glob("%s/*/commit.json" % args.source):
    with open(filename, 'r') as jsonfile:
        data = json.load(jsonfile)
        commits[data['id']] = data

# Load all necessary Criterion results. This iterates over all files
# holding Criterion estimates and populates a multi-level `estimates`
# dictionary mapping (group, chart, line, sha) quadruples derived from
# the path to estimate values we are interested in (e.g. median time).
#
# Note that we interpret the path as follows:
#   data / commit-<sha> / [<group> /] <line> / <chart>
#
#   <group> ... A thematic grouping of multiple charts ... "suite"
#   <chart> ... A graph holding multiple lines of data ... "benchmark"
#   <line>  ... A line of values over time/commits     ... "config"
estimates = {}
r = re.compile(r'^/(?:([^/]+)/)?([^/]+)/([^/]+)/new/estimates.json')
for sha in commits.keys():
    basedir = "%s/commit-%s" % (args.source, sha[0:8])
    jsonglob = "%s/**/new/estimates.json" % basedir
    for filename in glob.glob(jsonglob, recursive=True):
        m = r.search(filename[len(basedir):])
        (groupname, linename, chartname) = m.groups("")
        group = estimates.setdefault(groupname, {})
        chart = group.setdefault(chartname, {})
        line = chart.setdefault(linename, {})
        with open(filename, 'r') as jsonfile:
            data = json.load(jsonfile)
            line[sha] = data['median']['point_estimate']

# Determines the measurement unit best suited for all values in the
# given `pointset` (with time measurements in nanoseconds). Returns the
# appropriate unit name and divisor.
def normalized_unit(pointset):
    units = [("seconds (s)", 1000*1000*1000),
             ("millis (ms)", 1000*1000),
             ("micros (us)", 1000),
             ("nanos (ns)", 1)]
    minimal_point = min(map(min, pointset.values()));
    for (unit_name, unit_divisor) in units:
        if minimal_point > unit_divisor:
            return (unit_name, unit_divisor)

# Crunch the loaded data into a format that is easier to handle on the
# client-side. This produces a `perf` array meant to be serialized into
# JSON and be loaded by the JavaScript counterpart on the dashboard.
#
# Note that this transport format was chosen arbitrarily. Computation
# below represents the server-side, computation in the dashboard the
# client-side. Moving computation between the two sides will affect the
# trade-off between the size of data transmitted and the time spent on
# computation on the client. This boundary is fluid.
perf = []
time_sorted = sorted(commits.items(), key=lambda x: x[1]['timestamp'])
for (groupname, group) in sorted(estimates.items()):
    charts = [];
    for (chartname, chart) in sorted(group.items()) :
        lines = []; points = []; pointset = {};
        for (linename, line) in sorted(chart.items()):
            lines.append({ 'label': linename })
            for (pointname, point) in line.items():
              p = pointset.setdefault(pointname, [])
              p.insert(len(lines) - 1, point)
        (unitname, divisor) = normalized_unit(pointset)
        for (sha, commit) in time_sorted:
            if pointset.get(sha):
                data = [x / divisor for x in pointset[sha]]
                points.append({ 'label': sha[0:8],
                                'data': data})
        charts.append({ 'name': chartname,
                        'units': unitname,
                        'sets': lines,
                        'points': points })
    perf.append({ 'name': groupname, 'charts': charts })

# Serialize performance data into JSON format.
meta = { sha[0:8]: { 'message': commit['message'],
                     'timestamp': commit['timestamp'],
                     'author': commit['author']['name'] }
             for (sha, commit) in time_sorted }
data = { 'lastUpdate': int(time.time()),
         'perfGroups': perf,
         'commitMetadata': meta }
with open(args.output, 'w') as outfile:
    json.dump(data, outfile)
