"""
General Description
 
 *Tensor Fox* is a vast library of routines related to tensor problems. Since most tensor problems fall in the category of NP-hard problems [1], a great effort was made to make this library as efficient as possible. Some relevant routines and features of Tensor Fox are the following: 
 
 - Canonical polyadic decomposition (CPD)
 
 - High order singular value decomposition (HOSVD)
 
 - Multilinear rank
 
 - Rank estimate
 
 - Rank related statistics, including histograms
 
 - Rank related information about tensors and tensorial spaces
 
 - Convert tensors to matlab format
 
 - High performance with parallelism and GPU computation
 
 The CPD algorithm is based on the Damped Gauss-Newton method (dGN) with help of line search at each iteration in order to accelerate the convergence. We expect to make more improvements soon.
 
 All functions of Tensor Fox are separated in five categories: *Main*, *Construction*, *Conversion*, *Auxiliar*, *Display* and *Critical*. Each category has its own module, this keeps the whole project more organized. The main module is simply called *Tensor Fox*, since this is the module the user will interact to most of the time. The other modules have the same names as their categories. The construction module deals with constructing more complicated objects necessary to make computations with. The conversion module deals with conversions of one format to another. The auxiliar module includes minor function dealing with certain computations which are not so interesting to see at the main module. The display module has functions to display useful information. Finally, the critical module is not really a module, but a set of compiled Cython functions dealing with the more computationally demanding parts. We list all the functions and their respective categories below.
 
 **Main:** 
 
 - cpd
 
 - dGN 
 
 - hosvd
 
 - rank
 
 - stats
 
 - cg
 
 **Construction:**
 
 - residual
 
 - residual_entries
 
 - start_point
 
 - smart_random
 
 - smart_sample
 
 - assign_values
 
 - truncation
 
 - truncate1
 
 - truncate2
 
 **Conversion:**
 
 - x2cpd
 
 - cpd2tens
 
 - unfold

 - _unfold
 
 - foldback
 
 **Auxiliar:**
 
 - consistency
 
 - line_search

 - cpd_error

 - bissection 
 
 - multilin_mult
 
 - multirank_approx
 
 - refine
 
 - tens2matlab
 
 - _sym_ortho
 
 - update_damp

 - normalize

 - equalize
 
 **Display:**
 
 - showtens
 
 - infotens
 
 - infospace
 
 - rank1_plot
 
 - rank1
 
 **Critical:**
 
 - khatri_rao

 - gramians

 - hadamard

 - vec

 - vect

 - prepare_data

 - prepare_data_rmatvec

 - matvec

 - rmatvec

 - regularization

 - precond
 
 
 [1] C. J. Hillar and Lek-Heng Lim. Most Tensor Problems are NP-Hard. Journal of the ACM. 2013.
"""


import numpy as np
import sys
import scipy.io
import time
import matplotlib.pyplot as plt
from scipy import sparse
from numba import jit, njit, prange
import Construction as cnst
import Conversion as cnv
import Auxiliar as aux
import Display as disp
import Critical as crt


def cpd(T, r, energy=0.05, maxiter=200, tol=1e-6, init='smart_random', display='none'):
    """
    Given a tensor T and a rank R, this function computes one approximated CPD of T 
    with rank R. The result is given in the form [Lambda, X, Y, Z], where Lambda is a 
    vector and X, Y, Z are matrices. They are such that 
    sum_(l=1)^r Lambda[l] * X(l) ⊗ Y(l) ⊗ Z(l), 
    where X(l) denotes the l-th column of X. The same goes for Y and Z.

    Inputs
    ------
    T: float 3-D ndarray
        Objective tensor in coordinates.
    r: int 
        The desired rank of the approximating tensor.
    energy: float
        The energy varies between 0 and 100. For more information about how this parameter
    works, check the functions 'truncation', 'trancate1' and 'truncate2'. Default is 0.05.
    maxiter: int
        Number of maximum iterations allowed in the Gauss-Newton function. Default is 200.
    tol: float
        Tolerance criterium to stop the iteration proccess of the Gauss-Newton function.
    Default is 1e-4.
    init: string
        This options is used to choose the initial point to start the iterations. For more
    information, check the function 'init'. 
    display: string
        This options is used to control how information about the computations are displayed
    on the screen. For more information, check the function 'dGN'.
    
    Outputs
    -------
    Lambda: float 1-D ndarray with r entries
    X: float 2-D ndarray with shape (m,r)
    Y: float 2-D ndarray with shape (n,r)
    Z: float 2-D ndarray with shape (p,r)
        Lambda,X,Y,Z are such that (X,Y,Z)*Lambda ~ T.
    T_approx: float 3-D ndarray
        The approximating tensor in coordinates.
    err: float
        The relative error |T - T_approx|/|T| of the approximation computed. 
    step_sizes_trunc: float 1-D ndarray 
        Distance between the computed points at each iteration of the truncation stage.
    step_sizes_ref: float 1-D ndarray 
        Distance between the computed points at each iteration of the refinement stage.
    errors_trunc: float 1-D ndarray 
        Absolute error of the computed approximating tensor at each iteration of the 
    truncation stage.
    errors_ref: float 1-D ndarray 
        Absolute error of the computed approximating tensor at each iteration of the 
    refinement stage.
    """ 
        
    # Compute dimensions and norm of T.
    m_orig, n_orig, p_orig = T.shape
    m, n, p = m_orig, n_orig, p_orig
    T_orig = np.copy(T)
    Tsize = np.linalg.norm(T)
            
    # Test consistency of dimensions and rank.
    aux.consistency(r, m, n, p) 

    # Change ordering of indexes to improve performance if possible.
    T, ordering = aux.sort_dims(T, m, n, p)
    m, n, p = T.shape
    
    # COMPRESSION STAGE
    
    if display != 'none':
        print('------------------------------------------------------------------------------')
        print('Starting computation of the HOSVD of T.')
    
    # Compute compressed version of T with the HOSVD. We have that T = (U1,U2,U3)*S.
    S, multi_rank, U1, U2, U3, sigma1, sigma2, sigma3 = hosvd(T)
    R1, R2, R3 = multi_rank
        
    if display != 'none':
        print('------------------------------------------------------------------------------')
        
        if (R1,R2,R3) == (m,n,p):
            print('No compression detected.')                        
        else:
            print('Compression detected. Compressing from',T.shape,'to',S.shape)
            # Computation of relative error associated with compression.
            T_compress = aux.multilin_mult(S, U1, U2, U3, R1, R2, R3)
            rel_err = np.linalg.norm(T - T_compress)/Tsize
            print('Compression relative error =', rel_err)
            
    # TRUNCATION STAGE       
        
    if display != 'none':
        print('------------------------------------------------------------------------------')
        print('Starting truncation.')
    
    # Truncate S to obtain a small tensor S_trunc with less energy than S, but close to S.
    S_trunc, U1_trunc, U2_trunc, U3_trunc, best_energy, R1_trunc, R2_trunc, R3_trunc, rel_err = cnst.truncation(T, Tsize, S, U1, U2, U3, r, sigma1, sigma2, sigma3, energy)
    
    # Check if the truncation is valid (if truncate too much the problem becomes ill-posed).
    aux.consistency(r, R1_trunc, R2_trunc, R3_trunc) 
     
    if display != 'none':
        
        if best_energy == 100:
            print('No truncation detected.')             
        else:
            print('Truncation detected. Truncating from', S.shape, 'to', S_trunc.shape)
            print(np.round(best_energy,4),'% of the energy was retained.')
            print('Truncation relative error =', rel_err) 
            
    # GENERATION OF STARTING POINT STAGE
        
    # Generate initial to start dGN.
    X, Y, Z, rel_err = cnst.start_point(T, Tsize, S_trunc, U1_trunc, U2_trunc, U3_trunc, r, R1_trunc, R2_trunc, R3_trunc, init)      

    if display != 'none':
        print('------------------------------------------------------------------------------')
        
        if init == 'fixed':
            print('Initialization: fixed')
        elif init == 'random':
            print('Initialization: random')
        else:
            print('Initialization: smart random')
        
        print('Relative error of initial guess =', rel_err)   
    
    # DAMPED GAUSS-NEWTON STAGE 
    
    if display != 'none':
        print('------------------------------------------------------------------------------')
        print('Starting damped Gauss-Newton method.')

    # Compute the approximated tensor in coordinates with the dGN method.
    x, step_sizes_trunc, errors_trunc = dGN(S_trunc, X, Y, Z, r, maxiter=maxiter, tol=tol, display=display) 
    
    # Compute CPD of S_trunc, which shoud be close to the CPD of S.
    X, Y, Z = cnv.x2CPD(x, X, Y, Z, R1_trunc, R2_trunc, R3_trunc, r)
    
    # REFINEMENT STAGE
    
    if display != 'none':
        print('------------------------------------------------------------------------------') 
        print('Starting refinement.') 
        
    # Refine this CPD to be even closer to the CPD of S.
    X, Y, Z, step_sizes_refine, errors_refine = aux.refine(S, X, Y, Z, r, R1_trunc, R2_trunc, R3_trunc, maxiter=maxiter, tol=tol, display=display)
    
    # FINAL WORKS

    # Go back to the original dimensions of T.
    X, Y, Z, U1_sort, U2_sort, U3_sort = aux.unsort_dims(X, Y, Z, U1, U2, U3, ordering)
       
    # Use the orthogonal transformations to obtain the CPD of T.
    X = np.dot(U1_sort,X)
    Y = np.dot(U2_sort,Y)
    Z = np.dot(U3_sort,Z)
    
    # Compute coordinate representation of the CPD of T.
    T_aux = np.zeros((m_orig, n_orig, p_orig), dtype = np.float64)
    T_approx = cnv.CPD2tens(T_aux, X, Y, Z, m_orig, n_orig, p_orig, r)
        
    # Compute relative error of the approximation.
    rel_err = np.linalg.norm(T_orig - T_approx)/Tsize

    # Normalize X, Y, Z to have column norm equal to 1.
    Lambda, X, Y, Z = aux.normalize(X, Y, Z, r)
    
    # Display final informations.
    if display != 'none':
        print('------------------------------------------------------------------------------')
        print('Number of steps =',step_sizes_trunc.shape[0] + step_sizes_refine.shape[0])
        print('Final Relative error =', rel_err)
    
    return Lambda, X, Y, Z, T_approx, rel_err, step_sizes_trunc, step_sizes_refine, errors_trunc, errors_refine


def dGN(T, X, Y, Z, r, maxiter=200, tol=1e-6, display='none'):
    """
    This function uses the Damped Gauss-Newton method to compute an approximation of T 
    with rank r. An initial point to start the iterations must be given. This point is
    described by the ndarrays Lambda, X, Y, Z.
    
    The Damped Gauss-Newton method is iterative, updating a point x at each iteration.
    The last computed x is gives an approximate CPD in flat form, and from this we have
    the components to form the actual CPD. This program also gives some additional 
    information such as the size of the steps (distance between each x computed), the 
    absolute errors between the approximate and target tensor, and the path of solutions 
    (the points x computed at each iteration are saved). 

    Inputs
    ------
    T: float 3-D ndarray
    Lambda: Float 1-D ndarray with r entries
    X: float 2-D ndarray of shape (m,r)
    Y: float 2-D ndarray of shape (n,r)
    Z: float 2-D ndarray of shape (p,r)
    r: int. 
        The desired rank of the approximating tensor.
    maxiter: int
        Number of maximum iterations permitted. Default is 200 iterations.
    tol: float
        Tolerance criterium to stop the iteration proccess. Let S^(k) be the approximating 
    tensor computed at the k-th iteration an x^(k) be the point computed at the k-th 
    iteration. If we have |T - T_approx^(k)|/|T| < tol or |x^(k+1) - x^(k)| < tol, then 
    the program stops. Default is tol = 10**(-6).
    display: string
    
    Outputs
    -------
    x: float 1-D ndarray with r+3*r*n entries 
        Each entry represents the components of the approximating tensor in the CPD form.
    More precisely, x is a flattened version of the CPD, which is given by
    x = [Lambda[1],...,Lambda[r],X[1,1],...,X[m,1],...,X[1,r],...,X[m,r],Y[1,1],...,Z[p,r]].
    T_approx: float 3-D ndarray with m*n*p entries 
        Each entry represents the coordinates of the approximating tensor in coordinate form.
    step_sizes: float 1-D ndarray 
        Distance between the computed points at each iteration.
    errors: float 1-D ndarray 
        Error of the computed approximating tensor at each iteration. 
    """  
    
    # Compute dimensions and norm of T.
    m, n, p = T.shape
    Tsize = np.linalg.norm(T)
    
    # INITIALIZE RELEVANT VARIABLES
    
    # error is the current absolute error of the approximation.
    error = np.inf
    # damp is the damping factos in the damping Gauss-Newton method.
    damp = 2.0
    # v is an auxiliary value used to update the damping factor.
    v = 2.0
    # old_residualnorm is the previous error (at each iteration) obtained in the LSMR function.
    old_residualnorm = 0.0
    # cg_maxiter is the maximum number of iterations of the Conjugate Gradient.
    cg_maxiter = max( 10, min(m*n*p, r+r*(m+n+p))/10 )
    alpha = 1.0
        
    # INITIALIZE RELEVANT ARRAYS
    
    x = np.concatenate((X.flatten('F'), Y.flatten('F'), Z.flatten('F')))
    y = x
    step_sizes = np.zeros(maxiter)
    errors = np.zeros(maxiter)
    # T_aux is an auxiliary array used only to accelerate the CPD2tens function.
    T_aux = np.zeros((m, n, p), dtype = np.float64)
    # res is the array with the residuals (see the residual function for more information).
    res = np.zeros(m*n*p, dtype = np.float64)
    # These arrays are used to store CPD's for some choices of alpha in the line search function.
    X_low = np.zeros((m, r), dtype = np.float64)
    Y_low = np.zeros((n, r), dtype = np.float64)
    Z_low = np.zeros((p, r), dtype = np.float64)
    X_high = np.zeros((m, r), dtype = np.float64)
    Y_high = np.zeros((n, r), dtype = np.float64)
    Z_high = np.zeros((p, r), dtype = np.float64)

    # Update data for the next Gauss-Newton iteration.
    Gr_X, Gr_Y, Gr_Z, Gr_XY, Gr_XZ, Gr_YZ, V_Xt, V_Yt, V_Zt, V_Xt_dot_X, V_Yt_dot_Y, V_Zt_dot_Z, Gr_Z_V_Yt_dot_Y, Gr_Y_V_Zt_dot_Z, Gr_X_V_Zt_dot_Z, Gr_Z_V_Xt_dot_X, Gr_Y_V_Xt_dot_X, Gr_X_V_Yt_dot_Y, X_dot_Gr_Z_V_Yt_dot_Y, X_dot_Gr_Y_V_Zt_dot_Z, Y_dot_Gr_X_V_Zt_dot_Z, Y_dot_Gr_Z_V_Xt_dot_X, Z_dot_Gr_Y_V_Xt_dot_X, Z_dot_Gr_X_V_Yt_dot_Y, Gr_YZ_V_Xt, Gr_XZ_V_Yt, Gr_XY_V_Zt, B_X_v, B_Y_v, B_Z_v, B_XY_v, B_XZ_v, B_YZ_v, B_XYt_v, B_XZt_v, B_YZt_v, X_norms, Y_norms, Z_norms, gamma_X, gamma_Y, gamma_Z, Gamma = crt.prepare_data(m, n, p, r)
    
    if display == 'full':
        print('Iteration | Step Size | Rel Error | Line Search |  Alpha  |  Damp  | #CG iterations ')
    
    # BEGINNING OF GAUSS-NEWTON ITERATIONS
    
    for it in range(0,maxiter):      
        # Update of all residuals at x. 
        res = cnst.residual(res, T, X, Y, Z, r, m, n, p)
                                        
        # Keep the previous value of x and error to compare with the new ones in the next iteration.
        old_x = x
        old_error = error
        
        # Computation of the Gauss-Newton iteration formula to obtain the new point x + y, where x is the 
        # previous point and y is the new step obtained as the solution of min_y |Ay - b|, with 
        # A = Dres(x) and b = -res(x).         
        y, itn, residualnorm = cg(X, Y, Z, Gr_X, Gr_Y, Gr_Z, Gr_XY, Gr_XZ, Gr_YZ, V_Xt, V_Yt, V_Zt, V_Xt_dot_X, V_Yt_dot_Y, V_Zt_dot_Z, Gr_Z_V_Yt_dot_Y, Gr_Y_V_Zt_dot_Z, Gr_X_V_Zt_dot_Z, Gr_Z_V_Xt_dot_X, Gr_Y_V_Xt_dot_X, Gr_X_V_Yt_dot_Y, X_dot_Gr_Z_V_Yt_dot_Y, X_dot_Gr_Y_V_Zt_dot_Z, Y_dot_Gr_X_V_Zt_dot_Z, Y_dot_Gr_Z_V_Xt_dot_X, Z_dot_Gr_Y_V_Xt_dot_X, Z_dot_Gr_X_V_Yt_dot_Y, Gr_YZ_V_Xt, Gr_XZ_V_Yt, Gr_XY_V_Zt, B_X_v, B_Y_v, B_Z_v, B_XY_v, B_XZ_v, B_YZ_v, B_XYt_v, B_XZt_v, B_YZt_v, X_norms, Y_norms, Z_norms, gamma_X, gamma_Y, gamma_Z, Gamma, -res, m, n, p, r, damp, cg_maxiter)       
              
        # Try to improve the step with line search.
        alpha, error = aux.line_search(T, T_aux, X, Y, Z, X_low, Y_low, Z_low, X_high, Y_high, Z_high, x, y, m, n, p, r)
                        
        # Update point obtained by the iteration.         
        x = x + alpha*y
             
        # Update the vectors Lambda, X, Y, Z.
        X, Y, Z = cnv.x2CPD(x, X, Y, Z, m, n, p, r)
        
        # Update the damping parameter. If there is no improvement in the residual we can't update,
        # so we stop iterating in this case. 
        if old_residualnorm == residualnorm:
            step_sizes[it] = np.linalg.norm(x - old_x)   
            errors[it] = error
            break            
        else:
            damp, v = aux.update_damp(Tsize, damp, v, old_error, error, old_residualnorm, residualnorm, itn, cg_maxiter)
        
        # Set old residual to compare with the new one in the next iteration.
        old_residualnorm = residualnorm
        
        # Update arrays with relevant information about the current iteration.
        step_sizes[it] = np.linalg.norm(x - old_x)   
        errors[it] = error
        
        # Show information about current iteration.
        if display == 'full':
            if alpha == 1:
                print('   ',it+1,'    | ','{0:.5f}'.format(step_sizes[it]),' | ','{0:.5f}'.format(error/Tsize),' |  Fail   | ','{0:.4f}'.format(alpha),'| ','{0:.4f}'.format(damp), ' | ', itn+1)
            else:
                print('   ',it+1,'    | ','{0:.5f}'.format(step_sizes[it]),' | ','{0:.5f}'.format(error/Tsize),' |  Success   | ','{0:.4f}'.format(alpha),'|','{0:.4f}'.format(damp), '| ', itn+1)
        
        # After 3 iterations the program starts to verify if the size of the current step is smaller
        # than tol, or if the difference between the previous and the current relative errors are 
        # smaller than tol.
        if it >= 3:
            errors_diff = np.abs(errors[it] - errors[it-1])/Tsize
            if (step_sizes[it] < tol) or (errors_diff < tol):
                break
    
    # SAVE LAST COMPUTED INFORMATIONS
    
    step_sizes = step_sizes[0:it+1]
    errors = errors[0:it+1]
    
    return x, step_sizes, errors


@jit(nogil=True)
def hosvd(T): 
    """
    This function computes the High order singular value decomposition (HOSVD) of a tensor T.
    This decomposition is given by T = (U1,U2,U3)*S, where U1,U2,U3 are orthogonal vectors,
    S is the 'central' tensor and * is the multilinear multiplication. The HOSVD is a particular
    case of the Tucker decomposition.

    Inputs
    ------
    T: float 3-D ndarray

    Outputs
    -------
    S: float 3-D ndarray
        The central tensor.
    multirank: int 1-D ndarray
        Is the multilinear rank of T (also known as the Tucker rank).
    U1, U2, U3: float 2-D ndarrays
    sigma1, sigma2, sigma3: float 1-D arrays
        Each one of these array is an ordered list with the singular values of the respective 
    unfolding of T.
    """    

    # Compute dimensions of T.
    m, n, p = T.shape
    
    # If some singular value is smaller than 1/|T|^2, we assign its value to zero.
    tol = 1/np.sum(T**2)
    
    # Compute all unfoldings of T. 
    T1 = cnv.unfold(T, m, n, p, 1)
    T2 = cnv.unfold(T, m, n, p, 2)
    T3 = cnv.unfold(T, m, n, p, 3)
    
    # Compute reduced SVD of all unfoldings. Note that we have to verify if sigma1 is empty 
    # after introducing the tolerance criterium. If it is empty, than we go back to the 
    # original sigma1 and keep it unchanged.
    
    # REDUCED SVD'S OF ALL UNFOLDINGS
    
    # Unfolding mode 1.
    U1, S, Vh = np.linalg.svd(T1, full_matrices=False)
    sigma1 = S[S > tol]
    if np.sum(sigma1) == 0:
        sigma1 = S
        R1 = m
    else:
        R1 = np.sum(S > tol)
        U1 = U1[:,0:R1]
    
    # Unfolding mode 2.
    U2, S, Vh = np.linalg.svd(T2, full_matrices=False)
    sigma2 = S[S > tol]
    if np.sum(sigma2) == 0:
        sigma2 = S
        R2 = n
    else:
        R2 = np.sum(S > tol)
        U2 = U2[:,0:R2]
    
    # Unfolding mode 3.
    U3, S, Vh = np.linalg.svd(T3, full_matrices=False)
    sigma3 = S[S > tol]
    if np.sum(sigma3) == 0:
        sigma3 = S
        R3 = p
    else:
        R3 = np.sum(S > tol)
        U3 = U3[:,0:R3]
    
    # MULTILINEAR RANK
    
    multi_rank = np.array([R1,R2,R3])
    
    # CENTRAL TENSOR
    
    # Compute HOSVD of T, which is given by the identity S = (U1^T, U2^T, U3^T)*T.
    # S is the core tensor with size R1 x R2 x R3 and each Ui is an orthogonal matrix.
    S = np.zeros((R1,R2,R3))
    S = aux.multilin_mult(T, U1.transpose(), U2.transpose(), U3.transpose(), m, n, p)
        
    return S, multi_rank, U1, U2, U3, sigma1, sigma2, sigma3


def rank(T, display='full'):
    """
    This function computes several approximations of T for r = 1...n^2. We use 
    these computations to determine the (most probable) rank of T. The function also 
    returns an array `errors_per_rank` with the relative errors for the rank varying 
    from 1 to r+1, where r is the computed rank of T. It is relevant to say that the 
    value r computed can also be the `border rank` of T, not the actual rank. 

    The idea is that the minimum of \|T-S\|, for each rank r, stabilizes when S has 
    the same rank as T. This function also plots the graph of the errors so the user 
    are able to visualize the moment when the error stabilizes.
    
    Inputs
    ------
    T: float 3-D ndarray
    display: string
        There are two options: 'full' (default) and 'none'. The first one shows and
    plot informations while the second shows nothing.
    
    Outputs
    -------
    final_rank: int
        The computed rank of T.
    errors_per_rank: float 1-D ndarray
        The error |T-S| computed for each rank.    
    """
    
    # Compute dimensions and norm of T.
    m, n, p = T.shape
    Tsize = np.linalg.norm(T)
        
    # INITIALIZE RELEVANT VARIABLES
    
    # R is an upper bound for the rank.
    R = min(m*n, m*p, n*p)
    
    # INITIALIZE RELEVANT ARRAYS
    
    T_aux = np.zeros(T.shape, dtype = np.float64)
    error_per_rank = np.zeros(R)
    
    
    # Before the relevant loop for r=1...R, we compute the HOSVD of T and truncate it if possible.
    # This is exactly the first part of the cpd function. 
    
    # COMPRESSION STAGE
    
    S, multi_rank, U1, U2, U3, sigma1, sigma2, sigma3 = hosvd(T)
    R1, R2, R3 = multi_rank           
    
    # START THE PROCCESS OF FINDING THE RANK
    
    print('Start searching for rank')
    print('-------------------------------------------------------------------')
    print('Stops at r =',R,' or less')
    print()
    
    for r in range(1,R):  
        print('Trying r =',r)
            
        # TRUNCATION STAGE       
        
        S_trunc, U1_trunc, U2_trunc, U3_trunc, best_energy, R1_trunc, R2_trunc, R3_trunc, rel_err = cnst.truncation(T, Tsize, S, U1, U2, U3, r, sigma1, sigma2, sigma3, energy=99)
        
        # Generate starting point.
        X, Y, Z, rel_err = cnst.start_point(T, Tsize, S_trunc, U1_trunc, U2_trunc, U3_trunc, r, R1_trunc, R2_trunc, R3_trunc)      
        
        # Start Gauss-Newton iterations.
        x, step_sizes1, errors1 = dGN(S_trunc, X, Y, Z, r) 
        
        # Compute CPD of the point obtained.
        X, Y, Z = cnv.x2CPD(x, X, Y, Z, R1_trunc, R2_trunc, R3_trunc, r)
        
        # Refine solution.
        X, Y, Z, step_sizes2, errors2 = aux.refine(S, X, Y, Z, r, R1_trunc, R2_trunc, R3_trunc)
        
        # Put solution at the original space, where T lies.
        X = np.dot(U1,X)
        Y = np.dot(U2,Y)
        Z = np.dot(U3,Z)
        
        # Compute the solution in coordinates.
        T_approx = cnv.CPD2tens(T_aux, X, Y, Z, m, n, p, r)
    
        # Compute relative error of this approximation.
        err = np.linalg.norm(T - T_approx)/Tsize        
        error_per_rank[r-1] = err
        
        if r > 1:
            # Verification of the stabilization condition.
            if np.abs(error_per_rank[r-1] - error_per_rank[r-2]) < 1e-5:
                break
    
    # SAVE LAST INFORMATIONS
    
    final_rank = r-1
    error_per_rank = error_per_rank[0:r] 
    
    # DISPLAY AND PLOT ALL RESULTS
    
    print('Estimated rank(T) =',r-1)
    print('|T - T_approx|/|T| =',error_per_rank[-2])
    
    if display != 'none':
        plt.plot(range(1,r+1), np.log10(error_per_rank))
        plt.plot(r-1, np.log10(error_per_rank[-2]), marker = 'o', color = 'k')
        plt.title('Rank trials')
        plt.xlabel('r')
        plt.ylabel(r'$\log_{10} \|T - S\|/|T|$')
        plt.grid()
        plt.show()
            
    return final_rank, error_per_rank


def stats(T, r, maxit=200, tol=1e-4, num_samples = 100):
    """
    This function makes several calls of the Gauss-Newton function with random initial 
    points. Each call turns into a sample to recorded so we can make statistics lates. 
    By defalt this functions takes 100 samples to analyze. The user may choose the number
    of samples the program makes, but the computational time may be very costly. 
    Also, the user may choose the maximum number of iterations and the tolerance to be 
    used in each Gauss-Newton function.

    The outputs plots with general information about all the trials. These 
    informations are the following:

    * The total time spent in each trial.

    * The number of steps used in each trial.

    * The relative error |T-S|/|T| obtained in each trial.

    Inputs
    ------
    T: float 3-D ndarray
    r: int 
        The desired rank of the approximating tensor.
    maxiter: int
    tol: float
    """
    
    # Compute dimensions and norm of T.
    m, n, p = T.shape
    Tsize = np.linalg.norm(T)
    
    # INITIALIZE RELEVANT VARIABLES
    
    best_error = np.inf 
    
    # INITIALIZE RELEVANT ARRAYS
    
    times = np.zeros(num_samples)
    steps = np.zeros(num_samples)
    rel_errors = np.zeros(num_samples)
      
    # BEGINNING OF SAMPLING AND COMPUTING
    
    # At each run, the program computes a CPD for T with random guess for initial point.
    for trial in range(1, num_samples+1):            
        start = time.time()
        Lambda, X, Y, Z, T_approx, rel_err, step_sizes_trunc, step_sizes_ref, errors_trunc, errors_ref = cpd(T, r)
               
        # Update the vectors with general information.
        times[trial-1] = time.time() - start
        steps[trial-1] = step_sizes_trunc.shape[0] + step_sizes_ref.shape[0]
        rel_errors[trial-1] = rel_err
        
        if float(trial/num_samples) in np.arange(0.1, 1.1, 0.1):
            print(100*float(trial/num_samples), '%')
     
    # PLOT HISTOGRAMS
    
    [array,bins,patches] = plt.hist(times, 50)
    plt.xlabel('Seconds')
    plt.ylabel('Quantity')
    plt.title('Histogram of the total time of each trial')
    plt.show()

    [array,bins,patches] = plt.hist(steps, 50)
    plt.xlabel('Number of steps')
    plt.ylabel('Quantity')
    plt.title('Histogram of the number of steps of each trial')
    plt.show()

    [array,bins,patches] = plt.hist(np.log10(rel_errors), 50)
    plt.xlabel(r'$\log_{10} \|T-S\|/\|T\|$')
    plt.ylabel('Quantity')
    plt.title('Histogram of the log10 of the relative error of each trial')
    plt.show()

    return times, steps, rel_errors


@njit(nogil=True)
def cg(X, Y, Z, Gr_X, Gr_Y, Gr_Z, Gr_XY, Gr_XZ, Gr_YZ, V_Xt, V_Yt, V_Zt, V_Xt_dot_X, V_Yt_dot_Y, V_Zt_dot_Z, Gr_Z_V_Yt_dot_Y, Gr_Y_V_Zt_dot_Z, Gr_X_V_Zt_dot_Z, Gr_Z_V_Xt_dot_X, Gr_Y_V_Xt_dot_X, Gr_X_V_Yt_dot_Y, X_dot_Gr_Z_V_Yt_dot_Y, X_dot_Gr_Y_V_Zt_dot_Z, Y_dot_Gr_X_V_Zt_dot_Z, Y_dot_Gr_Z_V_Xt_dot_X, Z_dot_Gr_Y_V_Xt_dot_X, Z_dot_Gr_X_V_Yt_dot_Y, Gr_YZ_V_Xt, Gr_XZ_V_Yt, Gr_XY_V_Zt, B_X_v, B_Y_v, B_Z_v, B_XY_v, B_XZ_v, B_YZ_v, B_XYt_v, B_XZt_v, B_YZt_v, X_norms, Y_norms, Z_norms, gamma_X, gamma_Y, gamma_Z, Gamma, b, m, n, p, r, damp, cg_maxiter):
    
    Gr_X, Gr_Y, Gr_Z, Gr_XY, Gr_XZ, Gr_YZ = crt.gramians(X, Y, Z, Gr_X, Gr_Y, Gr_Z, Gr_XY, Gr_XZ, Gr_YZ)
    w_Xt, Mw_Xt, Bu_Xt, N_X, w_Yt, Mw_Yt, Bu_Yt, N_Y, w_Zt, Bu_Zt, Mu_Zt, N_Z = crt.prepare_data_rmatvec(X, Y, Z, m, n, p, r)
    M = np.ones(r*(m+n+p))
    L = np.ones(r*(m+n+p))
    L = crt.regularization(X, Y, Z, X_norms, Y_norms, Z_norms, gamma_X, gamma_Y, gamma_Z, Gamma, m, n, p, r)
    M = crt.precond(X, Y, Z, L, M, damp, m, n, p, r)
    
    y = np.zeros(r*(m+n+p), dtype = np.float64)
    residual = np.zeros(r*(m+n+p), dtype = np.float64)
    P = np.zeros(r*(m+n+p), dtype = np.float64)
    Q = np.zeros(r*(m+n+p), dtype = np.float64)
    z = np.zeros(r*(m+n+p), dtype = np.float64)
    
    residual = M*crt.rmatvec(X, Y, b, w_Xt, Mw_Xt, Bu_Xt, N_X, w_Yt, Mw_Yt, Bu_Yt, N_Y, w_Zt, Bu_Zt, Mu_Zt, N_Z, m, n, p, r)
    P = residual
    residualnorm = np.dot(residual, residual)
    residualnorm_new = 0.0
    alpha = 0.0
    beta = 0.0
    
    for itn in range(0, cg_maxiter):
        Q = M*P
        z = crt.matvec(X, Y, Z, Gr_X, Gr_Y, Gr_Z, Gr_XY, Gr_XZ, Gr_YZ, V_Xt, V_Yt, V_Zt, V_Xt_dot_X, V_Yt_dot_Y, V_Zt_dot_Z, Gr_Z_V_Yt_dot_Y, Gr_Y_V_Zt_dot_Z, Gr_X_V_Zt_dot_Z, Gr_Z_V_Xt_dot_X, Gr_Y_V_Xt_dot_X, Gr_X_V_Yt_dot_Y, X_dot_Gr_Z_V_Yt_dot_Y, X_dot_Gr_Y_V_Zt_dot_Z, Y_dot_Gr_X_V_Zt_dot_Z, Y_dot_Gr_Z_V_Xt_dot_X, Z_dot_Gr_Y_V_Xt_dot_X, Z_dot_Gr_X_V_Yt_dot_Y, Gr_YZ_V_Xt, Gr_XZ_V_Yt, Gr_XY_V_Zt, B_X_v, B_Y_v, B_Z_v, B_XY_v, B_XZ_v, B_YZ_v, B_XYt_v, B_XZt_v, B_YZt_v, Q, m, n, p, r) + damp*L*Q
        z = M*z
        alpha = residualnorm/np.dot(P.T, z)
        y += alpha*P
        residual = residual - alpha*z
        residualnorm_new = np.dot(residual, residual)
        beta = residualnorm_new/residualnorm
        residualnorm = residualnorm_new
        P = residual + beta*P
        if residualnorm < 1e-6:
            return M*y, itn, residualnorm   
        
    return M*y, itn+1, residualnorm


# Below we wrapped some functions which can be useful to the user. By doing this we just need to load the module TensorFox to do all the needed work.


def tens2matlab(T):    
    aux.tens2matlab(T)
    
    return


def CPD2tens(T_aux, X, Y, Z, m, n, p, r):
    T_aux = np.zeros((m,n,p), dtype = np.float64)
    T_aux = cnv.CPD2tens(T_aux, X, Y, Z, m, n, p, r)
    
    return T_aux


def residual_derivative_structure(r, m, n, p):
    data, row, col, datat_id, colt = cnst.residual_derivative_structure(r, m, n, p)
    
    return data, row, col, datat_id, colt


def showtens(T):
    disp.showtens(T)
    
    return


def infotens(T):
    disp.infotens(T)
    
    return


def infospace(m,n,p):
    disp.infospace(m,n,p)
    
    return


def rank1_plot(Lambda, X, Y, Z, r):
    disp.rank1_plot(Lambda, X, Y, Z, r)
    
    return
