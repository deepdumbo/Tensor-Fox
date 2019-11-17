"""
 Initialization Module
 ===================
 Module responsible for constructing the initializations, that is, the initial factor matrices.
"""

# Python modules
import numpy as np
from numpy import dot, empty, zeros, ones, int64, arange, sqrt, inf, argmax, array, prod, unravel_index
from numpy.linalg import norm
from numpy.random import randn, randint
import sys
from numba import njit

# Tensor Fox modules
import Conversion as cnv
import MultilinearAlgebra as mlinalg


def starting_point(T, Tsize, S, U, R, ordering, options):
    """
    This function generates a starting point to begin the iterations. There are three options:
        - list: the user may give a list with the factor matrices to be used as starting point.
        - 'random': the entries the factor matrices are generated by the normal distribution with mean 0 and variance 1.
        - 'smart_random': generates a random starting point with a method based on the MLSVD which always guarantee a 
           small relative error. Check the function 'smart_random' for more details about this method.
        - 'smart': works similar as the smart_random method, but this one is deterministic and generates the best rank-R
           approximation based on the MLSVD.
    
    Inputs
    ------
    T: float array
    Tsize: float
    S: float array
        The core tensor of the MLSVD of T.
    U: list of float 2-D arrays
        Each element of U is a orthogonal matrix of the MLSVD of T.
    R: int
        the desired rank.
    ordering: list of ints
       Since the cpd may change the index ordering, this list may be necessary if the user gives an initialization,
       which will be based on the original ordering.
    options: class
    
    Outputs
    -------
    init_factors: list of float 2-D arrays
    """

    # Extract all variable from the class of options.
    initialization = options.initialization
    low, upp, factor = options.constraints
    c = options.factors_norm
    symm = options.symm
    display = options.display
    dims = S.shape
    L = len(dims)

    if type(initialization) == list:
        init_factors = [dot(U[l].T, initialization[ordering[l]]) for l in range(L)]

    elif initialization == 'random':
        init_factors = [randn(dims[l], R) for l in range(L)]

    elif initialization == 'smart_random':
        init_factors = smart_random(S, dims, R)

    elif initialization == 'smart':
        init_factors = smart(S, dims, R)

    else:
        sys.exit('Error with init parameter.')

    # Depending on the tensor, the factors may have null entries. We want to avoid that. The solution is to introduce
    # a very small random noise.
    init_factors = clean_zeros(init_factors, dims, R)    
        
    # Make all factors balanced.
    init_factors = cnv.equalize(init_factors, R)

    # Apply additional transformations if requested.
    init_factors = cnv.transform(init_factors, low, upp, factor, symm, c)

    if display > 2 or display < -1:
        # Computation of relative error associated with the starting point given.
        S_init = cnv.cpd2tens(init_factors)
        S1_init = cnv.unfold(S_init, 1)
        rel_error = mlinalg.compute_error(T, Tsize, S1_init, U, dims)
        return init_factors, rel_error

    return init_factors


def smart_random(S, dims, R):
    """
    This function generates 1 + int(sqrt(prod(dims))) samples of random possible initializations. The closest to S is
    saved. This method draws R random points in S and generates a tensor with rank <= R from them. The distribution
    is such that it tries to maximize the energy of the sampled tensor, so the error is minimized.
    
    Inputs
    ------
    S: float array
        The core tensor of the MLSVD of T.
    dims: list or tuple
        The dimensions (shape) of S.
    R: int
        The desired rank.
        
    Outputs
    -------
    best_factors: list of float 2-D arrays
    """

    # Initialize auxiliary values and arrays.
    dims = array(dims)
    samples = 1 + int(sqrt(prod(dims)))
    best_error = inf
    S1 = cnv.unfold(S, 1)
    Ssize = norm(S)

    # Start search for a good initial point.
    for sample in range(samples):
        init_factors = smart_sample(S, dims, R)
        # Compute error.
        S1_init = empty(S1.shape)
        S1_init = cnv.cpd2unfold1(S1_init, init_factors)
        rel_error = norm(S1 - S1_init) / Ssize
        if rel_error < best_error:
            best_error = rel_error
            best_factors = init_factors.copy()

    return best_factors


def smart_sample(S, dims, R):
    """
    We consider a distribution that gives more probability to smaller coordinates. This is because these are associated 
    with more energy. As example, let S be a third order tensor of dimensions R1, R2, R3. First the program takes a
    random number c1 in the integer interval [0, R1 + (R1-1) + (R1-2) + ... + 1]. If 0 <= c1 < R1, then it takes
    i = 1, and if R1 <= c1 < R1 + (R1-1), it takes i = 2, and so on. The same goes for the other coordinates.
    Let S_{i_r,j_r,k_r}, r = 1...R, be the points chosen by this method. With them we can form the tensor
    S_init = sum_{r=1}^R S_{i_r,j_r,k_r} e_{i_r} ⊗ e_{j_r} ⊗ e_{k_r}, which should be close to S.
    
    Inputs
    ------
    S: float array
    dims: list or tuple
    R: int
    
    Ouputs
    ------
    init_factors: list of float 2-D arrays
    """

    L = len(dims)
    
    # Initialize arrays to construct initial approximate CPD.
    init_factors = [zeros((dims[l], R)) for l in range(L)]
    
    # Construct the upper bounds of the intervals.
    arr = [dims[l] * ones(dims[l]) - arange(dims[l]) for l in range(L)]
    high = [np.sum(arr[l]) for l in range(L)]

    # Arrays with all random choices.
    C = [randint(high[l], size=R) for l in range(L)]
    
    # Update arrays based on the choices made.
    for r in range(R):
        init_factors, idx = assign_values(init_factors, dims, C, arr, r)
        init_factors[0][idx[0], r] = S[tuple(idx)]

    return init_factors


@njit(nogil=True)
def assign_values(init_factors, dims, C, arr, r):
    """
    For each r = 1...R, this function constructs l-th one rank term in the CPD of the initialization tensor. For a third
    order tensor the rank one terms are of the form S[i,j,k]*e_i ⊗ e_j ⊗ e_k for some i,j,k choose through the random
    distribution described earlier.
    """
    
    L = len(dims)  
    idx = []
        
    for l in range(L):
        for i in range(dims[l]):
            if (np.sum(arr[l][0: i]) <= C[l][r]) and (C[l][r] < np.sum(arr[l][0: i + 1])):
                init_factors[l][i, r] = 1
                idx.append(i)
                break        

    return init_factors, idx


def smart(S, dims, R):
    """
    Construct a truncated version of S with the R entries with higher energy. For example consider a third order tensor
    S = sum_{i,j,k} S_{i,j,k} * e_{i_r} ⊗ e_{j_r} ⊗ e_{k_r}. First the program takes R coordinates S_{i,j,k} with the
    higher magnitudes and constructs the tensor S_init = sum_{r=1}^r S_{i_r,j_r,k_r} e_{i_r} ⊗ e_{j_r} ⊗ e_{k_r}, which
    should be close to S. Then it verifies if it is possible to reduce the number of rank 1 terms (this is possible just
    by verifying the indexes). In the positive case it is possible to add more entries, hence producing a tensor even
    closer to S.
    
    Inputs
    ------
    S: float array
    dims: list or tuple
    R: int
            
    Outputs
    -------
    init_factors: list of float 2-D arrays
    """

    L = len(dims)
    S_cp = np.abs(S).copy()
    idx = []
    modes = zeros(R, dtype=int64)

    # Put entries of S in decreasing order on the energy.
    for i in range(S.size):
        idx.append(unravel_index(argmax(S_cp), S_cp.shape))
        S_cp[idx[i]] = -inf

    final_idx = idx[:R].copy()
    idx = idx[R:]

    # Initialize the factors.
    init_factors = [zeros((dims[l], R)) for l in range(L)]

    previous_count = 0

    for i in range(100):    
        # Try to reduce number of rank 1 terms.
        count, joined = join_rank1(final_idx)
        
        # The counting process considers the previous matches and adds the new ones.
        # We discount the previous and only update if there is some new match.
        if count - previous_count <= 0:
            break

        # There are 'count' rank 1 terms to be included.
        final_idx = final_idx + idx[:count - previous_count]
        idx = idx[count - previous_count:]
        previous_count = count  
     
    rank1_idx = [[] for r in range(R)]
    r = 0
    for x in joined:
        for y in x:      
            rank1_idx[r].append(y)
            final_idx.remove(y)
        r += 1

    for x in final_idx:
        rank1_idx[r].append(x)
        r += 1

    # Initialize the factors.
    init_factors = [zeros((dims[l], R)) for l in range(L)]

    # Use the entries computed previously to generates the factors.
    for r in range(R):
        modes[r] = find_pivot(rank1_idx[r])
        for x in rank1_idx[r]:
            for l in range(L):
                if l == modes[r]:
                    init_factors[l][x[l], r] += S[x]
                else:
                    init_factors[l][x[l], r] = 1                 
    
    return init_factors


def join_rank1(idx):
    """
    This function verifies if the indexes of S_init (in th smart function) permit to reduce the number of rank 1 terms.
    For example, consider the tensor e_1 ⊗ e_1 ⊗ e_1 + e_1 ⊗ e_2 ⊗ e_1 + e_1 ⊗ e_3 ⊗ e_1 + e_2 ⊗ e_2 ⊗ e_2. From this
    tensor the function join_rank1 will produce the list final_joined = [ [(1,1,1), (1,2,1), (1,3,1)], [(2,2,2)] ],
    meaning that the first list in final_joined are tensor products which can be reduced to a single rank 1 term,
    whereas the second list (which is a singleton) cannot.

    Inputs
    ------
    idx: list of tuples
        Each element of idx is a tuple of with a single index of S. These tuples are ordered in descending order, such
        that the first ones correspond to the entries of S with higher magnitude.

    Outputs
    -------
    count: int
        Number of new entries of S included. Originally we only have R entries.
    final_joined: list of list of tuples
        Each element of final_joined is a list with the indexes of a single rank one term.
    """

    R = len(idx)
    L = len(idx[0])
    count = 0
    tmp = idx.copy()
    joined = [[] for i in range(L*R)]
    i = 0
    
    for l in range(L):
        indexes = [j for j in range(L) if j != l]
        r = 0
        
        while r < len(tmp):            
            # Extract all entries of idx[r] except the l-th one.
            term = tuple(tmp[r][j] for j in indexes)
            rr = r+1
                        
            while rr < len(tmp):
                term_tmp = tuple(tmp[rr][j] for j in indexes)
                if term_tmp == term:
                    joined[i].append(tmp[rr])
                    tmp.remove(tmp[rr])
                    count += 1
                rr += 1
                    
            if len(joined[i]) > 0:
                joined[i].append(tmp[r])
                tmp.remove(tmp[r])
                
            i += 1
            r += 1
            
    final_joined = [joined[i] for i in range(L*R) if len(joined[i]) > 0]    
                    
    return count, final_joined


def find_pivot(x):
    """
    Finds the pivot of a list of indexes computed in the function join_rank1. For example, consider the tensor
    e_1 ⊗ e_1 ⊗ e_1 + e_1 ⊗ e_2 ⊗ e_1 + e_1 ⊗ e_3 ⊗ e_1 + e_2 ⊗ e_2 ⊗ e_2. From this tensor the function join_rank1 will
    produce the list final_joined = [ [(1,1,1), (1,2,1), (1,3,1)], [(2,2,2)] ], meaning that the first list in
    final_joined are tensor products which can be reduced to a single rank 1 term, whereas the second list
    (which is a singleton) cannot. Let x = [(1,1,1), (1,2,1), (1,3,1)]. Then find_pivot(x) = 1, because this is the
    coordinate which is varying while the other are fixed (we could write [1, j, 1] for j=1,2,3 to represent x). Hence
    this is the pivot coordinate.
    Finding indexes with a single pivot coordinate matter because they translate from indexes to rank 1 terms. In the
    example above we can, informally, write (1,1,1) + (1,2,1) + (1,3,1) = (1, 1+2+3, 1), meaning that
    e_1 ⊗ e_1 ⊗ e_1 + e_1 ⊗ e_2 ⊗ e_1 + e_1 ⊗ e_3 ⊗ e_1 = e_1 ⊗ (e_1 + e_2 + e_3) ⊗ e_1.
    """

    if len(x) == 1:
        return 0
    
    x1 = x[0]
    x2 = x[1]
    for l in range(len(x1)):
        if x1[l] != x2[l]:
            return l        


def clean_zeros(init_factors, dims, R):
    """
    Any null entry is redefined to be a small random number.
    """

    # Initialize the factors X, Y, Z with small noises to avoid null entries.
    L = len(dims)
    
    for l in range(L):
        init_factors[l] = clean_mode_l(init_factors[l], dims[l], R)

    return init_factors


@njit(nogil=True)
def clean_mode_l(factor, dim, R):
    """ 
    Performs the cleaning stage for mode l.
    """
    
    for i in range(dim):
        for r in range(R):
            if factor[i, r] == 0.0:
                factor[i, r] = 1e-4 * randn() * norm(factor)
                
    return factor
