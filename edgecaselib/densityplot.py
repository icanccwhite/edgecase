from sys import stdout
from numpy import linspace, array, mean, nan, concatenate, fromiter
from pandas import read_csv, Series, concat
from matplotlib.pyplot import switch_backend, subplots
from seaborn import heatmap


def binned(A, bins, func=mean):
    """Return array data compressed into bins (smoothed by func)"""
    coords = linspace(0, len(A), bins+1).astype(int)
    return array([
        func(A[start:end])
        for start, end in zip(coords, coords[1:])
    ])


def load_metrics(dat, bin_size):
    """Load metrics from a text file, bin and convert into dataframe"""
    raw_data = read_csv(
        dat, compression="gzip", sep="\t",
        names=["name", "flag", "chrom", "pos", "mapq", "motif", "density"]
    )
    metadata = raw_data.iloc[:,:6]
    print(metadata[:3])
    exit(1)
    # old:
    read_metrics = {}
    # load and bin all metrics first:
    with open(dat, mode="rt") as handle:
        for line in handle:
            name, *metrics = line.strip().split("\t")
            metrics_array = fromiter(map(
                lambda s: float(s) if s!="" else nan,
                metrics
            ), dtype="float32")
            read_metrics[name] = binned(
                metrics_array,
                bins=len(metrics)/bin_size
            )
    # coerce to same lengths and convert into DataFrame:
    maxlen = max(len(d) for d in read_metrics.values())
    rows = []
    for name, metrics in read_metrics.items():
        padder = array([nan] * (maxlen - len(metrics)))
        if align == "left":
            padded_metrics = concatenate([metrics, padder])
        elif align == "right":
            padded_metrics = concatenate([padder, metrics])
        rows.append(Series(padded_metrics, name=name))
    return concat(rows, axis=1).T


def plot_metrics(metrics, figsize, palette, hide_names, bin_size, xtick_density, align="left", title="", png=stdout.buffer):
    """Plot binned metrics as a heatmap"""
    switch_backend("Agg")
    width, height = tuple(map(int, figsize.split("x")))
    figure, ax = subplots(figsize=(width, height))
    # force vmin and vmax for consistency between plots:
    heatmap(metrics, vmin=0, vmax=1, ax=ax, cmap=palette)
    # adjust xticks according to bin size and alignment:
    xticks = [
        int(tick.get_text()) for tick in ax.get_xticklabels()
    ]
    if align == "right":
        xticks = [
            tick * -1 for tick in reversed(xticks)
        ]
    if xtick_density != 1:
        each = int(len(xticks)*xtick_density)
        xticks = [
            xtick if i%each==0 else ""
            for i, xtick in enumerate(xticks)
        ]
    ax.set_xticklabels(
        [tick * bin_size for tick in xticks],
        rotation=60
    )
    # drop yticks (useful for long names / big sets):
    if hide_names:
        ax.set(yticks=[])
    ax.set(title=title, xlabel="position (bp)")
    figure.savefig(png)


def main(dat, bin_size=100, figsize="16x9", palette="viridis", hide_names=False, title=None, xtick_density=.05, file=stdout.buffer, **kwargs):
    """Dispatch data to subroutines"""
    metrics = load_metrics(dat, bin_size=bin_size)
    if title:
        title = title
    else:
        title = dat.split("/")[-1]
    plot_metrics(
        metrics, figsize, palette, hide_names,
        bin_size=bin_size,
        xtick_density=xtick_density, title=title, png=stdout.buffer
    )
    return 0
