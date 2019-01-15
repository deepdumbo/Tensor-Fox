"""
Construction Module
 
 As we mentioned in the main module *Tensor Fox*, the module *Construction* is responsible for constructing the more complicated objects necessary to make computations. Between these objects we have the array of residuals, the derivative of the residuals, the starting points to begin the iterations and so on. Below we list all funtions presented in this module.
 
 - residual
 
 - residual_entries
 
 - start_point
 
 - smart_random
 
 - smart_sample
 
 - assign_values

""" 


import numpy as np
import sys
import scipy.io
import time
import matplotlib.pyplot as plt
from scipy import sparse
from numba import jit, njit, prange
import Conversion as cnv
import Auxiliar as aux


@njit(nogil=True, parallel=True)
def residual(res, T, T_aux, m, n, p):
    """
    This function computes (updates) the residuals between a 3-D tensor T in R^m⊗R^n⊗R^p
    and an approximation T_approx of rank r. The tensor T_approx is of the form
    T_approx = Lambda_1*X_1⊗Y_1⊗Z_1 + ... + Lambda_r*X_r⊗Y_r⊗Z_r, where
    X = [X_1, ..., X_r],
    Y = [Y_1, ..., Y_r],
    Z = [Z_1, ..., Z_r].
    
    The `residual map` is a map res:R^{r+r(m+n+p)}->R^{m*n*p}. For each i,j,k=0...n, the residual 
    r_{i,j,k} is given by res_{i,j,k} = T_{i,j,k} - sum_{l=1}^r Lambda_l*X_{il}*Y_{jl}*Z_{kl}.
    
    Inputs
    ------
    res: float 1-D ndarray with m*n*p entries 
        Each entry is a residual.
    T: float 3-D ndarray
    T_aux: float 3-D ndarray
        T_aux is the current tensor obtained by the iteration of dGN. 
    m,n,p: int
    
    Outputs
    -------
    res: float 1-D ndarray with m*n*p entries 
        Each entry is a residual.
    """   
    
    s = 0
    
    #Construction of the vector res = (res_{111}, res_{112}, ..., res_{mnp}).
    for i in prange(0,m):
        for j in range(0,n):
            for k in range(0,p):
                s = n*p*i + p*j + k
                res[s] = T[i,j,k] - T_aux[i,j,k]
                            
    return res


@njit(nogil=True)
def residual_entries(T_ijk, X, Y, Z, r, i, j, k):
    """ 
    Computation of each individual residual in the residual function. 
    """
    
    acc = 0.0
    for l in range(0,r):
        acc += X[i,l]*Y[j,l]*Z[k,l]    
    
    res_ijk = T_ijk - acc
        
    return res_ijk


def start_point(T, Tsize, S, U1, U2, U3, r, R1, R2, R3, init, ordering, symm, display):
    """
    This function generates a starting point to begin the iterations of the
    Gauss-Newton method. There are three options:
        list: the user may give a list [X,Y,Z] with the three arrays to use
    as starting point.
        'random': each entry of Lambda, X, Y, Z are generated by the normal
    distribution with mean 0 and variance 1.
        'smart_random': generates a random starting point with a method which
    always guarantee a small relative error. Check the function 'smart' for 
    more details about this method.
    
    Inputs
    ------
    T: float 3-D ndarray
    Tsize: float
    S: float 3-D ndarray with shape (R1, R2, R3)
    U1: float 2-D ndarrays with shape (R1, r)
    U2: float 2-D ndarrays with shape (R2, r)
    U3: float 2-D ndarrays with shape (R3, r)
    r, R1, R2, R3: int
    init: string or list
       Method of initialization. The three methods were described above.
    symm: bool
    display: int
    
    Outputs
    -------
    Lambda: float 1-D ndarray with r entries
    X: float 2-D ndarray of shape (m, r)
    Y: float 2-D ndarray of shape (n, r)
    Z: float 2-D ndarray of shape (p, r)
    rel_error: float
        Relative error associate to the starting point. More precisely, it is the relative 
    error between T and (U1,U2,U3)*S_init, where S_init = (X,Y,Z)*Lambda.
    """
    
    if type(init) == list: 
        X = init[ordering[0]]
        Y = init[ordering[1]]
        Z = init[ordering[2]]  
        dims = [R1, R2, R3]
        X = X[:R1, :]
        Y = Y[:R2, :]
        Z = Z[:R3, :]
                
    elif init == 'random':
        X = np.random.randn(R1, r)
        Y = np.random.randn(R2, r)
        Z = np.random.randn(R3, r)
        
    elif init == 'smart_random':
        X, Y, Z = smart_random(S, r, R1, R2, R3)
        
    else:
        sys.exit('Error with init parameter.') 

    if symm:
        Y = X
        Z = X
    
    if display == 3:
        # Computation of relative error associated with the starting point given.
        T_aux = np.zeros(S.shape, dtype = np.float64)
        S_init = cnv.CPD2tens(T_aux, X, Y, Z, R1, R2, R3, r)
        rel_error = aux.compute_error(T, Tsize, S_init, R1, R2, R3, U1, U2, U3)
        return X, Y, Z, rel_error

    return X, Y, Z


def smart_random(S, r, R1, R2, R3):
    """
    100 samples of random possible initializations are generated and compared. We
    keep the closest to S_trunc. This method draws r points in S_trunc and generates
    a tensor with rank <= r from them. The distribution is such that it tries to
    maximize the energy of the sampled tensor, so the error is minimized.
    Althought we are using the variables named as R1, R2, R3, remember they refer to
    R1_trunc, R2_trunc, R3_trunc at the main function.
    Since this function depends on the energy, it only makes sense using it when the
    original tensor can be compressed. If this is not the case, avoid using this function.
    
    Inputs
    ------
    S: 3-D float ndarray
    r: int
    R1, R2, R3: int
        The dimensions of the truncated tensor S.
    samples: int
        The number of tensors drawn randomly. Default is 100.
        
    Outputs
    -------
    Lambda: float 1-D ndarray with r entries
    X: float 2-D ndarray of shape (m, R1)
    Y: float 2-D ndarray of shape (n, R2)
    Z: float 2-D ndarray of shape (p, R3)
    """
    
    # Initialize auxiliary values and arrays.
    samples = 1 + int(np.sqrt(R1*R2*R3))
    best_error = np.inf
    Ssize = np.linalg.norm(S)
    T_aux = np.zeros(S.shape, dtype = np.float64)

    # Start search for a good initial point.
    for sample in range(0,samples):
        X, Y, Z = smart_sample(S, r, R1, R2, R3)
        S_init = cnv.CPD2tens(T_aux, X, Y, Z, R1, R2, R3, r)
        rel_error = np.linalg.norm(S - S_init)/Ssize
        if rel_error < best_error:
            best_error = rel_error
            best_X, best_Y, best_Z = X, Y, Z

    # Depending on the tensor, the factors X, Y, Z may have null columns.
    # In the case this happens we introduce some random noise. 
    X_colsum = np.sum(best_X, axis=0)
    Y_colsum = np.sum(best_Y, axis=0)
    Z_colsum = np.sum(best_Z, axis=0)
    for l in range(0,r):
        max_X = np.max(X)
        max_Y = np.max(Y)
        max_Z = np.max(Z)
        if max_X == 0:
            max_X = 1
        if max_Y == 0:
            max_Y = 1
        if max_Z == 0:
            max_Z = 1
        if X_colsum[l] == 0:
            best_X[:,l] = (max_X/10)*np.random.randn(R1)
        if Y_colsum[l] == 0:
            best_Y[:,l] = (max_Y/10)*np.random.randn(R2)
        if Z_colsum[l] == 0:
            best_Z[:,l] = (max_Z/10)*np.random.randn(R3)

    return best_X, best_Y, best_Z


@jit(nogil=True)
def smart_sample(S, r, R1, R2, R3):
    """
    We consider a distribution that gives more probability to smaller coordinates. This 
    is because these are associated with more energy. We choose a random number c1 in the 
    integer interval [0, R1 + (R1-1) + (R1-2) + ... + 1]. If 0 <= c1 < R1, we choose i = 1,
    if R1 <= c1 < R1 + (R1-1), we choose i = 2, and so on. The same goes for the other
    coordinates.
    Let S_{i_l,j_l,k_l}, l = 1...r, be the points chosen by this method. With them we form
    the tensor S_init = sum_{l=1}^r S_{i_l,j_l,k_l} e_{i_l} ⊗ e_{j_l} ⊗ e_{k_l}, which 
    should be close to S_trunc.
    
    Inputs
    ------
    S: 3-D float ndarray
    r: int
    R1, R2, R3: int
    
    Ouputs
    ------
    Lambda: float 1-D ndarray with r entries
    X: float 2-D ndarray of shape (m, R1)
    Y: float 2-D ndarray of shape (n, R2)
    Z: float 2-D ndarray of shape (p, R3)
    """
    
    # Initialize arrays to construct initial approximate CPD.
    X = np.zeros((R1, r), dtype = np.float64)
    Y = np.zeros((R2, r), dtype = np.float64)
    Z = np.zeros((R3, r), dtype = np.float64)
    # Construct the upper bounds of the intervals.
    arr1 = R1*np.ones(R1, dtype = np.int64) - np.arange(R1)
    arr2 = R2*np.ones(R2, dtype = np.int64) - np.arange(R2)
    arr3 = R3*np.ones(R3, dtype = np.int64) - np.arange(R3)
    high1 = np.sum(arr1)
    high2 = np.sum(arr2)
    high3 = np.sum(arr3)

    # Arrays with all random choices.
    C1 = np.random.randint(high1, size=r)
    C2 = np.random.randint(high2, size=r)  
    C3 = np.random.randint(high3, size=r)

    # Update arrays based on the choices made.
    for l in range(0,r):
        X[:,l], Y[:,l], Z[:,l] = assign_values(S, X, Y, Z, r, R1, R2, R3, C1, C2, C3, arr1, arr2, arr3, l) 
          
    return X, Y, Z


@jit(nogil=True)
def assign_values(S, X, Y, Z, r, R1, R2, R3, C1, C2, C3, arr1, arr2, arr3, l):
    """
    For each l = 1...r, this function constructs l-th one rank term in the CPD of the
    initialization tensor, which is of the form S[i,j,k]*e_i ⊗ e_j ⊗ e_k for some
    i,j,k choosed through the random distribution described earlier.
    """
    
    for i in range(0,R1):
        if (np.sum(arr1[0:i]) <= C1[l]) and (C1[l] < np.sum(arr1[0:i+1])):
            X[i,l] = 1
            break
    for j in range(0,R2):
        if (np.sum(arr2[0:j]) <= C2[l]) and (C2[l] < np.sum(arr2[0:j+1])):
            Y[j,l] = 1
            break
    for k in range(0,R3):
        if (np.sum(arr3[0:k]) <= C3[l]) and (C3[l] < np.sum(arr3[0:k+1])):
            Z[k,l] = 1
            break   

    X[i,l] = S[i,j,k] 
        
    return X[:,l], Y[:,l], Z[:,l]