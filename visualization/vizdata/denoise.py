"""Module providing various Fourier and non-Fourier denoising strategies for
numeric data series.

Each denoising strategy is a closure that takes a number of passes as an
argument and returns a function that applies the corresponding denoising
technique to a list of numeric values. The number of passes controls the
strength of the denoising, with more passes resulting in stronger smoothing.
"""

import math
import statistics
from typing import Callable


# -- PRIVATE HELPERS ----------------------------------------------------------
def _pair(li: list[int | float]):
    """Pair up adjacent elements in a list, padding the last element if the
    list has an odd length.

    Args:
        li: List of numeric values to pair.

    Returns:
        List of tuples, where each tuple contains two adjacent values from the
        input list. If the input list has an odd length, the last tuple will
        contain the last element repeated.
    """
    pairs = [(li[i], li[i + 1]) for i in range(0, len(li) - 1, 2)]
    return pairs + [(li[-1], li[-1])] if len(li) % 2 == 1 else pairs


def _flatten(pairs: list[tuple[int | float, int | float]]):
    """Flatten a list of pairs into a single list of values.

    Args:
        pairs: List of tuples, where each tuple contains two numeric values.

    Returns:
        A single list containing all the values from the input pairs in order.
    """
    return [x for pair in pairs for x in pair]


def _sign(x: int | float):
    """Return the sign of a numeric value.

    Args:
        x: Numeric value to check.

    Returns:
        1 if x is positive, -1 if x is negative, and 0 if x is zero.
    """
    return math.copysign(1, x) if x != 0 else 0


_SQRT2 = math.sqrt(2)


# -- NON-FOURIER DENOISING STRATEGIES -----------------------------------------

def identity_denoise(passes: int = 1):
    """Return a function that performs no denoising and returns the input data
    as-is.

    Args:
        passes: Ignored; included for interface consistency with other
        denoising functions.

    Returns:
        A function that takes a list of numeric values and returns the same
        list unchanged.
    """
    def identity(data: list[int | float]):
        """Return the input data as-is without any denoising.

        Args:
            data: Sequence of numeric values.

        Returns:
            The same list of values unchanged.
        """
        return data

    return identity


def haar_denoise(passes: int = 1):
    """Return a function that applies a simple Haar wavelet transform to
    denoise a numeric series.

    Args:
        passes: The number of times to apply the Haar transform; more passes
        result in stronger denoising.

    Returns:
        A function that takes a list of numeric values and returns a denoised
        list of the same length.
    """
    def haar(data: list[int | float]):
        """Apply a simple Haar wavelet transform to denoise a numeric series.

        Args:
            data: Sequence of numeric values.

        Returns:
            List of denoised values.
        """
        # Return early if the input data is empty to avoid errors
        if len(data) == 0:
            return data

        # Store a list of the detail coefficients for reconstruction
        cD_list = []
        # Start with the approximations being the current data
        cAs = data

        # Cap passes at log_2(len(data)) to avoid adding ghost coefficients
        num_passes = min(passes, math.floor(math.log2(len(data))))

        # Track original length for padding during reconstruction
        original_length = len(data)

        # Compute the coefficients for the specified number of passes
        for _ in range(num_passes):
            # Pair up the current approximation list and pad as needed
            cA_pairs = _pair(cAs)
            # Compute each pass's detail coefficients
            cDs = [(x - y) / _SQRT2 for x, y in cA_pairs]

            # Apply a threshold to transform the detail coefficients
            abs_median = statistics.median(map(abs, cDs))
            sigma = abs_median / 0.67448975
            threshold = sigma * math.sqrt(2 * math.log(len(cDs)))
            cDs = [_sign(cD) * max(abs(cD) - threshold, 0) for cD in cDs]

            # Store the coefficients for reconstruction
            cD_list.append(cDs)
            # Compute the next approximation coefficients
            cAs = [(x + y) / _SQRT2 for x, y in cA_pairs]

        # Store the final computed approximations as the last layer
        # Reconstruct the denoised signal
        for coefficients in reversed(cD_list):
            inverse_pairs = [
                    ((cA + cD) / _SQRT2, (cA - cD) / _SQRT2)
                    for cA, cD in zip(cAs, coefficients)
                    ]
            cAs = _flatten(inverse_pairs)

        return cAs[:original_length]

    return haar


# -- FOURIER DENOISING STRATEGIES ---------------------------------------------


# -- CONSTANTS ----------------------------------------------------------------

DENOISING_STRATEGIES = {
    "identity": identity_denoise,
    "haar": haar_denoise
}


# -- UTILITY FUNCTIONS --------------------------------------------------------

def not_identity(callback: Callable[[list[int | float]], list[int | float]]):
    """Return whether the provided callback is not the identity denoising
    function.

    Args:
        callback: Denoising function to check.

    Returns:
        True if the callback is not the identity function; False if it is.
    """
    return callback.__qualname__ != identity_denoise(1).__qualname__
