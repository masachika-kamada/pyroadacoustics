import numpy as np
import math

class DelayLine:
    """
    Class that defines a variable length Delay Line. A delay line applies a delay of M samples
    to the input signal that is being written on the delay line. When the value of M varies at each
    sampling instant, it generates a continuously varying delay line, i.e. a delay line where the
    distance between the read pointer and the write pointer is a function of time.

    In order to take into account a smooth change in the delay length M, the read operation must rely
    on an interpolation in case the position of the read pointer falls between two samples of the delay
    line (i.e. M is a non-integer number, and the delay is thus fractional). Different interpolation
    methods (linear, Lagrange, sinc) result in different levels of accuracy.

    The variable length Delay Line can be used to simulate sound propagation if the delay varies according
    to the physical laws governing sound propagation.

    The delay line is represented by a circular `ndarray` of N samples, with a single write pointer performing
    write operations (one write per sampling interval), and an arbitrary number of read_pointers performing
    interpolated read operations (one operation per sampling interval per each pointer).

    Attributes
    ----------
    N: int
        Number of samples (i.e. entries) of the array defining the delay line
    delay_line: ndarray
        Circular array of N samples (i.e. entries) defining the delay line
    write_ptr: int
        Position of the write pointer that performs write operations on the delay line. Value must be in `[0, N-1]`
    read_ptr: float or ndarray
        Position of read pointers that perform read operations on the delay line. Each pointer value must be in
        `[0, N-1]`, and can take float values (interpolated reads operations are performed)
    interpolation: str
        Interpolation method to be used for fractional delay reads. Can be 'Linear', 'Lagrange' or 'Sinc'
    

    Methods
    -------
    set_delays(delay):
        Set initial read pointers position, as specified by the `delay` parameter (delay in number of samples)
    update_delay_line(x, delay):
        Writes signal value x on the delay line at the write_ptr position and increments write_ptr by 1.
        Performs interpolated read operation for each of the write pointers, and updates read pointer values
        based on the delay parameter (delay in number of samples)

    Notes
    -----
    A detailed description of the working principle of variable length delay lines is given in 
    
    `https://ccrma.stanford.edu/~jos/pasp/Variable_Delay_Lines.html`
    
    """

    def __init__(
            self, 
            N = 48000,
            num_read_ptrs = 1,
            interpolation = 'Linear',
        ):
        """
        Creates a Delay Line object as a `ndarray` of N samples, with one write pointer, M read pointers and
        a sampling frequency.

        Parameters
        ----------
        N : int, optional
            Number of samples (i.e. elements) of array defining the delay line, by default 48000
        num_read_ptrs : int, optional
            Number of pointers that will read values from the delay line, by default 1. The `write_ptr` attribute
            will be instantiated as an 1D `ndarray` having num_read_pointers float entries.
        interpolation : str, optional
            String describing the type of interpolator to be used for fractional delay read operations. Can be:
            * Linear: linear interpolation
            * Lagrange: Lagrange interpolation with order 5
            * Sinc: sinc interpolation with filter length of 11 taps
            
            By default: 'Linear'
        
        Raises
        ------
        ValueError:
            If `N` is negative or equal to zero
        ValueError:
            If `num_read_ptrs` <= 0
        ValueError:
            If `interpolation` is neither Linear, nor Sinc, nor Lagrange
        """

        if N <= 0:
            raise ValueError("Delay Line size must be greater than zero.")
        if num_read_ptrs <= 0:
            raise ValueError("Number of read pointers must be greater than zero.")
        if interpolation != 'Linear' and interpolation != "Lagrange" and interpolation != "Sinc":
            raise ValueError("Interpolation parameter can be: `Linear`, `Lagrange`, or `Sinc`")

        self.N = N
        self.write_ptr = 0
        self.read_ptr = np.zeros(num_read_ptrs, dtype=float)
        self.delay_line = np.zeros(N)
        self.interpolation = interpolation

    def set_delays(self, delay: np.ndarray) -> None:
        """
        Sets initial delays between the write pointer and each of the read pointers in the delay line.

        Parameters
        ----------
        delay : np.array(dtype = float)
            1D Array with number of elements equal to number of read pointers of the delay line. Each entry 
            is the delay in number of samples between the write pointer and each of read pointers, and can
            take non-integer positive values.

        Raises
        ------
        ValueError:
            If one or more elements of the delay array is zero or negative
        ValueError:
            If len(delay) is different from number of read pointers
        RuntimeError:
            If one or more elements of the delay array are greater than the length of the delay line
        """

        if np.any(delay <= 0):
            raise ValueError('Delays must be non-negative numbers')
        if len(delay) != len(self.read_ptr):
            raise ValueError('Length of delay array should match number of read pointers')
        if np.any(delay >= self.N):
            raise RuntimeError('Delay greater than delay line length has been encountered. Consider'
            'using a longer delay line')
        
        for i in range(len(self.read_ptr)):
            self.read_ptr[i] = self.write_ptr - delay[i]
            # Check that read pointer value is in [0, N-1]
            if (self.read_ptr[i] < 0):
                self.read_ptr[i] += self.N

    def update_delay_line(self, x: float, delay: np.ndarray) -> np.ndarray:
        """
        Writes signal value x on the delay line at the write_ptr position and increments write_ptr by 1.
        Performs interpolated read operation for each of the write pointers, and updates read pointer values
        based on the delay parameter (delay in number of samples).

        Parameters
        ----------
        x : float
            Input signal sample to be written on delay line at write pointer position
        delay : np.ndarray
            1D Array with number of elements equal to number of read pointers of the delay line. Each entry 
            is the delay in number of samples between the write pointer and each of read pointers, and can
            take non-integer positive values.

        Returns
        -------
        np.ndarray
            1D Array containing 1 interpolated read sample per each of the read pointers of the delay line. These 
            values represent the output of the delay line (i.e. a delayed version of the input signal, interpolated
            to take into account fractional values of the delay)
        """
        
        # Create array to store output values
        y = np.zeros_like(self.read_ptr)

        # Append input sample at the write pointer position and increment write pointer
        self.delay_line[self.write_ptr] = x
        self.write_ptr += 1

        for i in range(len(self.read_ptr)):
            # Compute interpolated read position (fractional delay)
            rpi = int(np.floor(self.read_ptr[i]))
            frac_del = self.read_ptr[i] - rpi
        
            # Produce output with interpolated read
            y[i] = self._interpolated_read(rpi, frac_del, self.interpolation)

            # Update read pointer position
            self.read_ptr[i] = self.write_ptr - delay[i]
            # Check that read and write pointers are within delay line length
            while (self.read_ptr[i] < 0):
                self.read_ptr[i] += self.N
            while (self.write_ptr >= self.N):
                self.write_ptr -= self.N
            while (self.read_ptr[i] >= self.N):
                self.read_ptr[i] -= self.N
        return y

    def _interpolated_read(self, read_ptr_integer: int, d: float, method: str = 'Linear') -> float:
        """
        Produce interpolated read from delay line. Read pointer position is given to this function as an
        integer part (`read_ptr_integer`) and a fractional part (`d`) in [0,1]. The interpolation is 
        operated considering neighbouring samples of the signal on the delay line and using the method
        specified in the `method` parameter.
        
        Parameters
        ----------
        read_ptr_integer : int
            Integer part of the delay
        d : float
            Fractional part of the delay, in the interval [0,1]
        method : str, optional
            Interpolation method used, by default 'Linear'. Can be:
            * Linear: linear interpolation, uses 2 neighbouring samples
            * Lagrange: Lagrange polynomial interpolation, order 5 can be changed in this function. Implemented
            using an FIR filter
            * Sinc: sinc interpolation, implemented using windowed truncated sinc FIR filter with 11 taps. Window
            and number of taps can be modified in this function

        Returns
        -------
        float
            Sample computed after interpolated read, as a single float value

        Raises
        ------
        ValueError:
            If `method` is neither `Linear`, nor `Lagrange`, nor `Sinc`
        """
        
        # TODO Vectorization to speed up convolution

        if method == 'Lagrange':
            # Compute interpolation filter
            order = 5
            h_lagrange = self._frac_delay_lagrange(order, d)
            
            # Convolve signal with filter
            out = 0
            for i in range(0, len(h_lagrange)):
                out = out + h_lagrange[i] * self.delay_line[np.mod(read_ptr_integer + i - math.floor(order/2), self.N)]
            return out

        elif method == 'Linear':
            # Linear Interpolation formula
            return d * self.delay_line[np.mod(read_ptr_integer + 1, self.N)] + (1 - d) * self.delay_line[read_ptr_integer]

        elif method == 'Sinc':
            # Define windowed sinc filter paramters and compute coefficients
            sinc_samples = 11
            sinc_window = np.hanning(sinc_samples)
            h_sinc = self._frac_delay_sinc(sinc_samples, sinc_window, d)
            # TODO: Implement sinc lookup with linear interpolation to speed up computations
            
            # Convolve signal with filter
            out = 0
            for i in range(0, sinc_samples):
                out = out + h_sinc[i]*self.delay_line[np.mod(read_ptr_integer + i - math.floor(sinc_samples/2), self.N)]
            return out

        else:
            raise ValueError("Interpolation parameter can be: `Linear`, `Lagrange`, or `Sinc`")
    
    def _frac_delay_lagrange(self, order: int, delay: float) -> np.ndarray:
        """
        Computes Lagrange fractional delay FIR filter coefficients.

        Parameters
        ----------
        order : int
            Filter order. Must be an odd number, number of taps will be order + 1
        delay : float
            Fractional part of the delay

        Returns
        -------
        np.ndarray
            1D Array containing (order + 1) FIR filter coefficients
        """

        n = np.arange(0, order + 1)
        h = np.ones(order + 1)

        for k in range(0, order + 1):
            # Find index n != k
            index = []
            for j in range(0, order + 1):
                if j != k:
                    index.append(j)
            
            h[index] = h[index] * (delay - k) / (n[index] - k)
        return h
    
    def _frac_delay_sinc(self, sinc_samples: int, sinc_window: np.ndarray, delay: float) -> np.ndarray:
        """
        Computes windowed sinc FIR filter coefficients for sinc interpolation.

        Parameters
        ----------
        sinc_samples : int
            Number of taps of the filter, should be an odd number
        sinc_window : np.ndarray
            Window to be applied to sinc function. Length of the window must be equal to sinc_samples
        delay : float
            Fractional part of the delay

        Returns
        -------
        np.ndarray
            1D array containing `sinc_samples` FIR filter coefficients
        """
        return sinc_window * np.sinc(np.arange(0,sinc_samples) - (sinc_samples - 1) / 2 - delay)
