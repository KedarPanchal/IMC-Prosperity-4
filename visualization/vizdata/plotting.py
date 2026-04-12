"""Helper functions for plotting with matplotlib."""

import matplotlib.pyplot as plt
from typing import Any


# -- PRIVATE HELPERS ----------------------------------------------------------

def _formatter(value: Any, discard: Any):
    """Format a numeric value as an integer string for axis ticks."""
    return f"{int(value)}"


# -- PLOTTING FUNCTIONS -------------------------------------------------------

def make_plots(title: str, rows: int, cols: int, denoised: bool):
    """Create a subplot grid and a full-width bottom axis for combined series.

    The last row of the grid is removed and replaced by ``axes_master``, which
    spans the figure width for overlaying all items.

    Args:
        title: Figure suptitle.
        rows: Number of subplot rows requested before the bottom strip is
        repurposed.
        cols: Number of columns.

    Returns:
        ``(fig, axes, axes_master)`` where ``axes`` is the remaining grid
        (without the bottom row) and ``axes_master`` is the bottom summary
        axis.
    """
    fig, axes = plt.subplots(rows, cols, figsize=(16, 8), squeeze=False)
    fig.suptitle(title)

    for ax in axes[-1]:
        ax.remove()
    axes_master = fig.add_subplot(rows, 1, rows)
    axes_master.set_title(f"All Items{' (denoised)' if denoised else ''}")
    axes_master.xaxis.set_major_formatter(_formatter)
    axes_master.yaxis.set_major_formatter(_formatter)

    return fig, axes, axes_master


def plot_data(
        axis,
        timestamps: list[int],
        data: list[int | float],
        data_label: str,
        data_color: str,
        artists: list,
        axis_color: str | None = None,
        title: str | None = None,
        title_color: str | None = None,
        show_legend: bool = False
        ):
    """Plot one series on an axis and append line artists for interactive 
    cursors.

    Args:
        axis: Target matplotlib axes.
        timestamps: X coordinates.
        data: Y coordinates.
        data_label: Label used in the legend when enabled.
        data_color: Line color.
        artists: Mutable list extended with the line artist(s) from this plot.
        axis_color: If set, colors the y-axis tick labels.
        title: If set with ``title_color``, used as the y-axis label.
        title_color: Color for the y-axis label when ``title`` is provided.
        show_legend: Whether to call ``legend()`` on the axis.

    Returns:
        None.
    """
    axis.xaxis.set_major_formatter(_formatter)
    axis.yaxis.set_major_formatter(_formatter)
    if title and title_color:
        axis.set_ylabel(title, color=title_color)
    plot = axis.plot(
        timestamps,
        data,
        linewidth=0.8,
        label=data_label,
        color=data_color,
        picker=8
    )
    artists.extend(plot)

    if axis_color:
        axis.tick_params(axis="y", labelcolor=axis_color)
    if show_legend:
        axis.legend()
