from sys import stdout
from os import path
from edgecaselib.formats import load_index, filter_bam
from pysam import AlignmentFile
from functools import reduce
from operator import __or__
from copy import deepcopy
from edgecaselib.tailpuller import get_bam_chunk
from edgecaselib.util import progressbar
from numpy import inf


__doc__ = """edgeCase tailpuller-10x: selection of candidate telomeric read clouds

Usage: {0} tailpuller-10x -x filename [-f flagspec] [-g flagspec] [-F flagspec]
       {1}                [-q integer] [-m integer] <bam>

Output:
    SAM-formatted file with read clouds extending past anchors defined in index

Positional arguments:
    <bam>                             name of input BAM/SAM file; must have a .bai index

Required options:
    -x, --index [filename]            location of the reference .ecx index

Options:
    -m, --max-hmw-length [integer]    maximum HMW length to consider when selecting lookup regions

Input filtering options:
    -f, --flags [flagspec]            process only entries with all these sam flags present [default: 0]
    -g, --flags-any [flagspec]        process only entries with any of these sam flags present [default: 65535]
    -F, --flag-filter [flagspec]      process only entries with none of these sam flags present [default: 0]
    -q, --min-quality [integer]       process only entries with this MAPQ or higher [default: 0]
"""

__docopt_converters__ = [
    lambda min_quality:
        None if (min_quality is None) else int(min_quality),
    lambda max_hmw_length:
        inf if (max_hmw_length is None) else int(max_hmw_length),
]

__docopt_tests__ = {
    lambda bam:
        path.isfile(bam + ".bai"): "BAM index (.bai) not found",
    lambda max_hmw_length:
        max_hmw_length > 0: "--max-hmw-length below 0",
}


def get_terminal_pos(entry, cigarpos):
    """Calculate the position of clipped start/end of read relative to the reference"""
    if not entry.cigartuples: # no CIGAR available
        return None
    # measure the clipped stretch on the left (0) or right (-1):
    cigartype, clip = entry.cigartuples[cigarpos]
    if (cigartype != 4) and (cigartype != 5): # not a soft/hard clip
        clip = 0
    # determine location of start/end of the read relative to reference:
    if cigarpos == 0: # start
        return entry.reference_start - clip
    elif cigarpos == -1: # end
        return entry.reference_end + clip
    else:
        raise ValueError("get_terminal_pos(): cigarpos can only be 0 or -1")


def updated_entry(entry, flags, is_q=False):
    """Add ECX flags to entry"""
    new_entry = deepcopy(entry)
    new_entry.flag |= reduce(__or__, flags)
    if is_q:
        new_entry.flag |= 0x8000
    return new_entry


def main(bam, index, flags, flags_any, flag_filter, min_quality, max_hmw_length, file=stdout, **kwargs):
    # dispatch data to subroutines:
    raise NotImplementedError
    ecxfd = load_index(index, as_filter_dict=True)
    samfilters = [flags, flags_any, flag_filter, min_quality]
    with AlignmentFile(bam) as bam_data:
        reflens = dict(zip(bam_data.references, bam_data.lengths))
        print(str(bam_data.header).rstrip("\n"), file=file)
        decorated_bam_iterator = progressbar(
            ecxfd, total=len(ecxfd), desc="Pulling", unit="chromosome"
        )
        for chrom in decorated_bam_iterator:
            bam_chunk = get_bam_chunk(
                bam_data, chrom, ecxfd, reflens, max_hmw_length
            )
            for entry in filter_bam(bam_chunk, samfilters):
                if entry.reference_name in ecxfd:
                    print(entry)