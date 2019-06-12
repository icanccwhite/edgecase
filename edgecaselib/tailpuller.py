from sys import stdout
from re import compile, IGNORECASE
from edgecaselib.util import ReadFileChain
from edgecaselib.util import MAINCHROMS_ENSEMBL, MAINCHROMS_UCSC, MAINCHROMS_T2T
from tqdm import tqdm
from pysam import FastxFile, AlignmentFile
from pandas import read_csv, DataFrame
from itertools import takewhile, filterfalse


class AutofillableSet(set):
    def __contains__(self, item):
        self.add(item)
        return True


def get_mainchroms(names):
    """Choose mainchroms based on reference annotation format"""
    if names == "t2t":
        return MAINCHROMS_T2T
    elif names == "ucsc":
        return MAINCHROMS_UCSC
    elif names == "ensembl":
        return MAINCHROMS_ENSEMBL
    elif names == "riethman":
        return AutofillableSet()
    else:
        raise ValueError("Unsupported value of `names`")


def get_anchors(reference, mainchroms):
    """Get coordinates of hard-masked bounds at each end of each main chromosome"""
    if reference.endswith(".tsv"): # assume precomputed anchors
        anchors = read_csv(reference, sep="\t", index_col=0)
    else:
        pattern = compile(r'[^n]', flags=IGNORECASE)
        anchor_data = {}
        bar = tqdm(
            desc="Finding anchors", total=len(mainchroms), unit="chromosome"
        )
        with FastxFile(reference) as genome:
            for entry in genome:
                if entry.name in mainchroms:
                    bar.update()
                    bound_5prime = pattern.search(entry.sequence).span()[0]
                    bound_3prime = (
                        len(entry.sequence) -
                        pattern.search(entry.sequence[::-1]).span()[0]
                    )
                    anchor_data[entry.name] = bound_5prime, bound_3prime
        anchors = DataFrame(data=anchor_data, index=["5prime", "3prime"]).T
    return anchors, set(mainchroms)


def is_good_entry(entry, mainchroms):
    """Simple filter"""
    if entry.is_unmapped or entry.is_secondary or entry.is_supplementary:
        return False
    elif entry.reference_name in mainchroms:
        return True
    else:
        return False


def filter_entries(bam_data, anchors, prime, mainchroms):
    """Only pass reads extending past anchors"""
    isnone = lambda p: p is None
    for entry in bam_data:
        if is_good_entry(entry, mainchroms):
            positions = entry.get_reference_positions(full_length=True)
            left_clip = sum(
                True for _ in takewhile(isnone, positions)
            )
            left_mappos = next(filterfalse(isnone, positions))
            right_clip = sum(
                True for _ in takewhile(isnone, reversed(positions))
            )
            right_mappos = next(filterfalse(isnone, reversed(positions)))
            if prime not in {5, 3}:
                raise ValueError("`prime` can only be 5 or 3")
            elif prime == 5:
                anchor = anchors.loc[entry.reference_name, "5prime"]
                if left_mappos - left_clip < anchor:
                    yield entry
            elif prime == 3:
                anchor = anchors.loc[entry.reference_name, "3prime"]
                if right_mappos + right_clip > anchor:
                    yield entry


def main(bams, reference, prime, names, hmm=None, file=stdout, **kwargs):
    # use header of first input file (NB! fragile):
    with AlignmentFile(bams[0]) as bam:
        print(str(bam.header).rstrip("\n"), file=file)
    # dispatch data to subroutines:
    mainchroms = get_mainchroms(names)
    anchors, mainchroms = get_anchors(reference, mainchroms)
    if anchors.shape[0] == 0:
        raise ValueError("No anchors found (wrong -n parameter?)")
    with ReadFileChain(bams, AlignmentFile) as bam_data:
        for entry in filter_entries(bam_data, anchors, prime, mainchroms):
            print(entry.to_string(), file=file)
