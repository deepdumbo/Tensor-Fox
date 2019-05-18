"""
 Aternating Least Squares Module
 ===============================
 This module implement the Aternating Least Squares algorithm for third order tensors. The idea is to use it to compute
biCPD's for the tensor train.  
"""

# Python modules
import numpy as np
from numpy import inf, mean, copy, concatenate, empty, float64, sqrt, dot
from numpy.linalg import norm, pinv
from decimal import Decimal
from numba import njit

# Tensor Fox modules
import Auxiliar as aux
import Conversion as cnv
import Dense as dns
import MultilinearAlgebra as mlinalg 

def als(T, X, Y, Z, r, options):
    """
    This function uses the ALS method to compute an approximation of T with rank r. An initial point to 
    start the iterations must be given. This point is described by the arrays X, Y, Z. This program also 
    gives some additional information such as the size of the steps (distance between each x computed), the absolute 
    errors between the approximate and target tensor, and the path of solutions (the points x computed at each iteration 
    are saved). 

    Inputs
    ------
    T: float 3-D ndarray
    X: float 2-D ndarray of shape (m,r)
    Y: float 2-D ndarray of shape (n,r)
    Z: float 2-D ndarray of shape (p,r)
    r: int. 
        The desired rank of the approximating tensor.
    maxiter: int
        Number of maximum iterations permitted. 
    tol: float
        Tolerance criterium to stop the iteration proccess. This value is used in more than one stopping criteria.
    symm: bool
    display: int
    
    Outputs
    -------
    X, Y, Z: 2-D ndarray
        The factor matrices of the CPD of T.
    step_sizes: float 1-D ndarray 
        Distance between the computed points at each iteration.
    errors: float 1-D ndarray 
        Error of the computed approximating tensor at each iteration. 
    improv: float 1-D ndarray
        Improvement of the error at each iteration. More precisely, the difference between the relative error of the current 
        iteration and the previous one.
    gradients: float 1-D ndarray
        Gradient of the error function at each iteration.
    stop: 0, 1, 2, 3 or 4
        This value indicates why the dGN function stopped. Below we summarize the cases.
        0: step_sizes[it] < tol. This means the steps are too small.
        1: improv < tol. This means the improvement in the error is too small.
        2: gradients[it] < tol. This means the gradient is close enough to 0.
        3: mean(abs(errors[it-k : it] - errors[it-k-1 : it-1]))/Tsize < 10*tol. This means the average of the last k 
           relative errors is too small. Keeping track of the averages is useful when the errors improvements are just a 
           little above the threshold for a long time. We want them above the threshold indeed, but not too close for a 
           long time. 
        4: limit of iterations reached.
        5: no refinement was performed (this is not really a stopping condition, but it is necessary to indicate when the
        program can't give a stopping condition in the refinement stage).
        6: dGN diverged. 
    """  

    # INITIALIZE RELEVANT VARIABLES 

    # Extract all variable from the class of options.
    symm = options.symm 
    display = options.display
    low, upp, factor = options.constraints
    c = options.constant_norm
    method_info = options.method_parameters
    
    # Verify if some factor should be fixed or not. This nnly happens in the bicpd function.
    fix_mode = -1
    T1 = cnv.unfold(T, 1, T.shape)
    T2 = cnv.unfold(T, 2, T.shape)
    T3 = cnv.unfold(T, 3, T.shape)
    if type(X) == list:
        fix_mode = 0
        X_orig = copy(X[0])
        X = X[0]
        method_info = options.bi_method_parameters
    elif type(Y) == list:
        fix_mode = 1
        Y_orig = copy(Y[0])
        Y = Y[0]
        method_info = options.bi_method_parameters
    elif type(Z) == list:
        fix_mode = 2
        Z_orig = copy(Z[0])
        Z = Z[0]
        method_info = options.bi_method_parameters
                
    # Set the other variables.
    m, n, p = T.shape
    Tsize = norm(T)
    method, maxiter, tol = method_info 
    error = 1
    best_error = inf
    stop = 4
    const = 1 + int(maxiter/10)
                               
    # INITIALIZE RELEVANT ARRAYS
    
    x = concatenate((X.flatten('F'), Y.flatten('F'), Z.flatten('F')))
    grad = empty(r*(m+n+p), dtype = float64)
    step_sizes = empty(maxiter)
    errors = empty(maxiter)
    improv = empty(maxiter)
    gradients = empty(maxiter)
    T_approx = empty((m,n,p), dtype=float64)
    T_approx = cnv.cpd2tens(T_approx, [X, Y, Z], (m, n, p))

    if display > 1:
        if display == 4:
            print('   ', 
                  '{:^9}'.format('Iteration'), 
                  '| {:^11}'.format('Rel error'),
                  '| {:^11}'.format('Improvement'),
                  '| {:^11}'.format('norm(grad)'))
        else:
            print('   ', 
                  '{:^9}'.format('Iteration'), 
                  '| {:^9}'.format('Rel error'),
                  '| {:^10}'.format('Improvement'),
                  '| {:^10}'.format('norm(grad)'))                
    
    # START ALS ITERATIONS
    
    for it in range(maxiter):      
        # Keep the previous value of x and error to compare with the new ones in the next iteration.
        old_x = x
        old_error = error
                       
        # ALS iteration call.
        X, Y, Z = als_iteration(T1, T2, T3, X, Y, Z, m, n, p, r, fix_mode) 
        x = concatenate((X.flatten('F'), Y.flatten('F'), Z.flatten('F')))
                                     
        # Transform factors X, Y, Z.
        X, Y, Z = cnv.transform(X, Y, Z, m, n, p, r, low, upp, factor, symm, c)
        if fix_mode == 0:
            X = copy(X_orig)
        elif fix_mode == 1:
            Y = copy(Y_orig)
        elif fix_mode == 2:
            Z = copy(Z_orig)
                                          
        # Compute error. 
        T_approx = cnv.cpd2tens(T_approx, [X, Y, Z], (m, n, p)) 
        error = norm(T - T_approx)/Tsize

        # Update best solution.
        if error < best_error:
            best_error = error
            best_x = copy(x)
            best_X = copy(X)
            best_Y = copy(Y)
            best_Z = copy(Z)
                           
        # Save relevant information about the current iteration.
        step_sizes[it] = norm(x - old_x)
        errors[it] = error
        gradients[it] = np.abs(old_error - error)/step_sizes[it]
        if it == 0:
            improv[it] = errors[it]
        else:
            improv[it] = np.abs(errors[it-1] - errors[it])

        # Show information about current iteration.
        if display > 1:
            if display == 4:
                print('    ', 
                  '{:^8}'.format(it+1), 
                  '| {:^10.5e}'.format(errors[it]),
                  '| {:^10.5e}'.format(improv[it]),
                  '| {:^11.5e}'.format(gradients[it]))
            else:
                print('   ', 
                  '{:^9}'.format(it+1), 
                  '| {:^9.2e}'.format(errors[it]),
                  '| {:^11.2e}'.format(improv[it]),
                  '| {:^10.2e}'.format(gradients[it]))
           
        # Stopping conditions.
        if it > 1:
            if step_sizes[it] < tol:
                stop = 0
                break
            if improv[it] < tol:
                stop = 1
                break
            if gradients[it] < tol:
                stop = 2
                break 
            # Let const=1 + int(maxiter/10). If the average of the last const error improvements is less than 10*tol, then 
            # we stop iterating. We don't want to waste time computing with 'almost negligible' improvements for long time.
            if it > const and it%const == 0: 
                if mean(np.abs(errors[it-const : it] - errors[it-const-1 : it-1])) < 10*tol:
                    stop = 3
                    break  
            # Prevent blow ups.
            if error > max(1, Tsize**2)/tol:
                stop = 6
                break 
    
    # SAVE LAST COMPUTED INFORMATIONS
    
    step_sizes = step_sizes[0:it+1]
    errors = errors[0:it+1]
    improv = improv[0:it+1]
    gradients = gradients[0:it+1]
    
    return best_X, best_Y, best_Z, step_sizes, errors, improv, gradients, stop


@njit(nogil=True)
def als_iteration(T1, T2, T3, X, Y, Z, m, n, p, r, fix_mode):
    """
    This function makes two or three ALS iterations, that is, it computes the pseudoinverse with respect to 
    two or three modes depending if one of the modes is fixed. The implementation is simple and not intended 
    to be optimal. 
    """
    
    if fix_mode == -1:
        X = dot( T1, pinv(mlinalg.khatri_rao(Z, Y).T) )
        Y = dot( T2, pinv(mlinalg.khatri_rao(Z, X).T) )
        Z = dot( T3, pinv(mlinalg.khatri_rao(Y, X).T) )
        
    elif fix_mode == 0:
        Y = dot( T2, pinv(mlinalg.khatri_rao(Z, X).T) )
        Z = dot( T3, pinv(mlinalg.khatri_rao(Y, X).T) )
        
    elif fix_mode == 1:
        X = dot( T1, pinv(mlinalg.khatri_rao(Z, Y).T) )
        Z = dot( T3, pinv(mlinalg.khatri_rao(Y, X).T) )
        
    elif fix_mode == 2:
        X = dot( T1, pinv(mlinalg.khatri_rao(Z, Y).T) )
        Y = dot( T2, pinv(mlinalg.khatri_rao(Z, X).T) )
        
    return X, Y, Z