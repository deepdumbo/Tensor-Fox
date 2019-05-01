"""
 Gauss-Newton Module
 ===================
 This module implement the 'damped Gauss-Newton' algorithm, with iterations performed with aid of the conjugate gradient 
method.
"""

# Python modules
import numpy as np
from numpy import inf, mean, copy, concatenate, empty, zeros, ones, float64, sqrt, dot, arange, hstack, identity, diag
from numpy.linalg import norm, lstsq, LinAlgError
from numpy.linalg import solve as numpy_solve
from numpy.random import randn, randint
from scipy.linalg import solve
from decimal import Decimal
import sys
from numba import njit, prange
import matplotlib.pyplot as plt

# Tensor Fox modules
import Auxiliar as aux
import Conversion as cnv
import Dense as dns
import MultilinearAlgebra as mlinalg

def dGN(T, X, Y, Z, r, options):
    """
    This function uses the Damped Gauss-Newton method to compute an approximation of T with rank r. An initial point to 
    start the iterations must be given. This point is described by the arrays X, Y, Z.    
    The Damped Gauss-Newton method is a iterative method, updating a point x at each iteration. The last computed x is 
    gives an approximate CPD in flat form, and from this we have the components to form the actual CPD. This program also 
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
    x: float 1-D ndarray with r+3*r*n entries 
        Each entry represents the components of the approximating tensor in the CPD form. More precisely, x is a flattened 
        version of the CPD, which is given by
    x = [X[1,1],...,X[m,1],...,X[1,r],...,X[m,r],Y[1,1],...,Z[p,r]].
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
        2: gradients[it] < sqrt(tol). This means the gradient is close enough to 0.
        3: mean(abs(errors[it-k : it] - errors[it-k-1 : it-1]))/Tsize < 10*tol. This means the average of the last k 
           relative errors is too small. Keeping track of the averages is useful when the errors improvements are just a 
           little above the threshold for a long time. We want them above the threshold indeed, but not too close for a 
           long time. 
        4: limit of iterations reached.
        5: no refinement was performed (this is not really a stopping condition, but it is necessary to indicate when the
        program can't give a stopping condition in the refinement stage).
        6: dGN diverged. 
    """  

    # Verify if X should be fixed or not.
    fix_X = False
    if type(X) == list:
        fix_X = True
        X_orig = copy(X[0])
        X = X[0]
    
    # INITIALIZE RELEVANT VARIABLES 

    # Extract all variable from the class of options.
    init_damp = options.init_damp
    maxiter = options.maxiter 
    tol = options.tol
    symm = options.symm 
    display = options.display
    low, upp, factor = options.constraints
    method_info = options.method_parameters
                
    # Set the other variables.
    m, n, p = T.shape
    Tsize = norm(T)
    error = 1
    best_error = inf
    stop = 4
    damp = init_damp*mean(np.abs(T))
    old_damp = damp
    const = 1 + int(maxiter/10)
                               
    # INITIALIZE RELEVANT ARRAYS
    
    x = concatenate((X.flatten('F'), Y.flatten('F'), Z.flatten('F')))
    y = zeros(r*(m+n+p), dtype = float64)
    grad = empty(r*(m+n+p), dtype = float64)
    res = empty(m*n*p, dtype = float64)
    step_sizes = empty(maxiter)
    errors = empty(maxiter)
    improv = empty(maxiter)
    gradients = empty(maxiter)
    T_approx = empty((m,n,p), dtype=float64)
    T_approx = cnv.cpd2tens(T_approx, [X, Y, Z], (m, n, p))

    # Prepare data to use in each Gauss-Newton iteration.
    data = prepare_data(m, n, p, r)    
    data_rmatvec = prepare_data_rmatvec(m, n, p, r)
    lsmr_data = lsmr_prepare_data(X, Y, Z, m, n, p, r)
       
    if display > 1:
        if display == 4:
            print('   ', 
                  '{:^9}'.format('Iteration'), 
                  '| {:^11}'.format('Rel error'),
                  '| {:^11}'.format('Improvement'),
                  '| {:^11}'.format('norm(grad)'),
                  '| {:^11}'.format('Predicted error'),
                  '| {:^10}'.format('# Inner iterations'))
        else:
            print('   ', 
                  '{:^9}'.format('Iteration'), 
                  '| {:^9}'.format('Rel error'),
                  '| {:^10}'.format('Improvement'),
                  '| {:^10}'.format('norm(grad)'),
                  '| {:^10}'.format('Predicted error'),
                  '| {:^10}'.format('# Inner iterations'))                
    
    # START GAUSS-NEWTON ITERATIONS
    
    for it in range(maxiter):      
        # Update all residuals at x. 
        res = residual(res, T, T_approx, m, n, p)                
                                        
        # Keep the previous value of x and error to compare with the new ones in the next iteration.
        old_x = x
        old_error = error
                       
        # Computation of the Gauss-Newton iteration formula to obtain the new point x + y, where x is the 
        # previous point and y is the new step obtained as the solution of min_y |Ay - b|, with 
        # A = Dres(x) and b = -res(x). 
        y, grad, itn, residualnorm = compute_step(X, Y, Z, lsmr_data, data, data_rmatvec, y, grad, res, m, n, p, r, damp, method_info, it)  
                                     
        # Update point obtained by the iteration.         
        x = x + y
        
        # Compute factors X, Y, Z.
        X, Y, Z = cnv.x2cpd(x, X, Y, Z, m, n, p, r)
        X, Y, Z = cnv.transform(X, Y, Z, m, n, p, r, low, upp, factor, symm)
        if fix_X == True:
            X = copy(X_orig)
                                          
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
                           
        # Update damp. 
        old_damp = damp
        damp = update_damp(damp, old_error, error, residualnorm)
        
        # Save relevant information about the current iteration.
        step_sizes[it] = norm(x - old_x)
        errors[it] = error
        gradients[it] = norm(grad, inf)
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
                  '| {:^11.5e}'.format(gradients[it]),
                  '| {:^15.5e}'.format(residualnorm),
                  '| {:^16}'.format(itn))
            else:
                print('   ', 
                  '{:^9}'.format(it+1), 
                  '| {:^9.2e}'.format(errors[it]),
                  '| {:^11.2e}'.format(improv[it]),
                  '| {:^10.2e}'.format(gradients[it]),
                  '| {:^15.2e}'.format(residualnorm),
                  '| {:^16}'.format(itn))
           
        # Stopping conditions.
        if it > 1:
            if step_sizes[it] < tol:
                stop = 0
                break
            if improv[it] < tol:
                stop = 1
                break
            if gradients[it] < sqrt(tol):
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


def compute_step(X, Y, Z, lsmr_data, data, data_rmatvec, y, grad, res, m, n, p, r, damp, method_info, it):
    """    
    This function uses the adequate method to compute the step based on the user choice, otherwise the default
    (lsmr for small tensors and cg for big ones) is used.
    """
    
    method, method_maxiter, method_tol = method_info   
    inner_maxiter = 1 + int( method_maxiter * randint(1 + it**0.4, 2 + it**0.9) )
    inner_tol = method_tol
    
    if method == 'cg': 
        y, grad, itn, residualnorm = cg(X, Y, Z, data, data_rmatvec, y, grad, -res, m, n, p, r, damp, inner_maxiter, inner_tol)
    elif method == 'cg_static':
        y, grad, itn, residualnorm = cg(X, Y, Z, data, data_rmatvec, y, grad, -res, m, n, p, r, damp, method_maxiter, inner_tol)
    elif method == 'lsmr':
        y, grad, itn, residualnorm = lsmr(X, Y, Z, -res, lsmr_data, m, n, p, r, atol=inner_tol, btol=inner_tol, maxiter=inner_maxiter)
    elif method == 'lsmr_static':
        y, grad, itn, residualnorm = lsmr(X, Y, Z, -res, lsmr_data, m, n, p, r, atol=inner_tol, btol=inner_tol, maxiter=method_maxiter)
    else:
        sys.exit('Wrong method parameter specification.')

    return y, grad, itn, residualnorm


def lsmr(X, Y, Z, b, data, m, n, p, r, atol=0, btol=0, maxiter=100):
    """
    LSMR stands for 'least squares with minimal residual'. This LSMR function is an 
    adaptation of the scipy's LSMR function. You can see the original in the link below:
    https://docs.scipy.org/doc/scipy-0.14.0/reference/generated/scipy.sparse.linalg.lsmr.html
    
    The principal changes are in the matrix-vector multiplications. They are specialized to 
    this particular tensor problem, where the sparse matrix has some special structure. We
    use the arrays data and col to refer to Dres, and the arrays datat and colt to refer to 
    Dres.transpose.
    
    Inputs
    ------
    data, col, datat, colt: 1-D float ndarrays with 4*m*n*p*r entries each
    b: 1-D float ndarray
        b will receive the array -res
    r, m, n, p: int
    damp: float
        Damping factor for regularized least-squares. This LSMR solves
    the regularized least-squares problem min_x |Ax - b| + damp*|x|
    where | | is the Euclidean norm, A = Dres, b = -res and 
    x = (Lambda, X, Y, Z) - (Lambda^0, X^0, Y^0, Z^0). We have that 
    (Lambda^0, X^0, Y^0, Z^0) is the flattened CPD computed in the previous
    iteration and (Lambda, X, Y, Z) are the variables to be obtained by the
    minimization above.
    atol, btol : float
        Stopping tolerances. `lsmr` continues iterations until a
        certain backward error estimate is smaller than some quantity
        depending on atol and btol.  Let ``r = b - Ax`` be the
        residual vector for the current approximate solution ``x``.
        If ``Ax = b`` seems to be consistent, ``lsmr`` terminates
        when ``norm(r) <= atol * norm(A) * norm(x) + btol * norm(b)``.
        Otherwise, lsmr terminates when ``norm(A^{T} r) <=
        atol * norm(A) * norm(r)``.  If both tolerances are 1.0e-6 (say),
        the final ``norm(r)`` should be accurate to about 6
        digits. (The final x will usually have fewer correct digits,
        depending on ``cond(A)`` and the size of LAMBDA.)  If `atol`
        or `btol` is None, a default value of 1.0e-6 will be used.
        Ideally, they should be estimates of the relative error in the
        entries of A and B respectively.  For example, if the entries
        of `A` have 7 correct digits, set atol = 1e-7. This prevents
        the algorithm from doing unnecessary work beyond the
        uncertainty of the input data.
    maxiter : int
        `lsmr` terminates if the number of iterations reaches
        `maxiter`.  The default is ``maxiter = 100``.  For
        ill-conditioned systems, a larger value of `maxiter` may be
        needed.
        
    Outputs
    -------
    x : ndarray of float
        Least-square solution returned.
    istop : int
        istop gives the reason for stopping::
          istop   = 0 means x=0 is a solution.
                  = 1 means x is an approximate solution to A*x = B,
                      according to atol and btol.
                  = 2 means x approximately solves the least-squares problem
                      according to atol.
                  = 3 means COND(A) seems to be greater than CONLIM.
                  = 4 is the same as 1 with atol = btol = eps (machine
                      precision)
                  = 5 is the same as 2 with atol = eps.
                  = 6 is the same as 3 with CONLIM = 1/eps.
                  = 7 means ITN reached maxiter before the other stopping
                      conditions were satisfied.
    itn : int
        Number of iterations used.
    normr : float
        ``norm(b-Ax)``
    normar : float
        ``norm(A^T (b - Ax))``
    norma : float
        ``norm(A)``
    conda : float
        Condition number of A.
    normx : float
        ``norm(x)``
    """

    maxiter = min(maxiter, r*(m+n+p))

    # Update data for the next Gauss-Newton iteration.
    w_X, Bv_X, M_X, w_Y, Mw_Y, Bv_Y, M_Y, w_Z, Bv_Z, M_Z, w_Xt, Bu_Xt, w_Yt, Bu_Yt, w_Zt, Bu_Zt = data
    M_X, M_Y, M_Z = update_data_rmatvec(X, Y, Z, M_X, M_Y, M_Z)
    damp = 0
    
    # Initialize arrays.
    u = b
    beta = norm(u)
    v = zeros(r*(m+n+p), dtype = np.float64)
    alpha = 0

    if beta > 0:
        u = (1 / beta) * u
        v = rmatvec(u, w_Xt, Bu_Xt, M_X, w_Yt, Bu_Yt, M_Y, w_Zt, Bu_Zt, M_Z, m, n, p, r)
        alpha = norm(v)

    if alpha > 0:
        v = (1 / alpha) * v

    grad = copy(v)

    # Initialize variables for 1st iteration.
    itn = 0
    zetabar = alpha * beta
    alphabar = alpha
    rho = 1
    rhobar = 1
    cbar = 1
    sbar = 0

    h = copy(v)
    hbar = zeros(r*(m+n+p), dtype = np.float64)
    x = zeros(r*(m+n+p), dtype = np.float64)

    # Initialize variables for estimation of ||r||.
    betadd = beta
    betad = 0
    rhodold = 1
    tautildeold = 0
    thetatilde = 0
    zeta = 0
    d = 0

    # Initialize variables for estimation of ||A|| and cond(A).
    normA2 = alpha * alpha
    maxrbar = 0
    minrbar = 1e+100
    normA = sqrt(normA2)
    condA = 1
    normx = 0

    # Items for use in stopping rules.
    normb = beta
    istop = 0
    ctol = 0
    normr = beta

    # Reverse the order here from the original matlab code because
    # there was an error on return when arnorm==0.
    normar = alpha * beta
    if normar == 0:
        return x, istop, itn, normr, normar, normA, condA, normx

    # Main iteration loop.
    while itn < maxiter:
        itn = itn + 1

        # Perform the next step of the bidiagonalization to obtain the
        # next  beta, u, alpha, v.  These satisfy the relations
        #         beta*u  =  a*v   -  alpha*u,
        #        alpha*v  =  A'*u  -  beta*v.

        u = lsmr_matvec(X, Y, v, w_X, Bv_X, M_X, w_Y, Mw_Y, Bv_Y, M_Y, w_Z, Bv_Z, M_Z, m, n, p, r) - alpha * u
        beta = norm(u)

        if beta > 0:
            u = (1 / beta) * u
            v = rmatvec(u, w_Xt, Bu_Xt, M_X, w_Yt, Bu_Yt, M_Y, w_Zt, Bu_Zt, M_Z, m, n, p, r) - beta * v
            alpha = norm(v)
            if alpha > 0:
                v = (1 / alpha) * v

        # At this point, beta = beta_{k+1}, alpha = alpha_{k+1}.

        # Construct rotation Qhat_{k,2k+1}.
        chat, shat, alphahat = sym_ortho(alphabar, damp)

        # Use a plane rotation (Q_i) to turn B_i to R_i.
        rhoold = rho
        c, s, rho = sym_ortho(alphahat, beta)
        thetanew = s*alpha
        alphabar = c*alpha

        # Use a plane rotation (Qbar_i) to turn R_i^T to R_i^bar.
        rhobarold = rhobar
        zetaold = zeta
        thetabar = sbar * rho
        rhotemp = cbar * rho
        cbar, sbar, rhobar = sym_ortho(cbar * rho, thetanew)
        zeta = cbar * zetabar
        zetabar = - sbar * zetabar

        # Update h, h_hat, x.
        hbar = h - (thetabar * rho / (rhoold * rhobarold)) * hbar
        x = x + (zeta / (rho * rhobar)) * hbar
        h = v - (thetanew / rho) * h

        # Estimate of ||r||.

        # Apply rotation Qhat_{k,2k+1}.
        betaacute = chat * betadd
        betacheck = -shat * betadd

        # Apply rotation Q_{k,k+1}.
        betahat = c * betaacute
        betadd = -s * betaacute

        # Apply rotation Qtilde_{k-1}.
        # betad = betad_{k-1} here.

        thetatildeold = thetatilde
        ctildeold, stildeold, rhotildeold = sym_ortho(rhodold, thetabar)
        thetatilde = stildeold * rhobar
        rhodold = ctildeold * rhobar
        betad = - stildeold * betad + ctildeold * betahat

        # betad   = betad_k here.
        # rhodold = rhod_k  here.

        tautildeold = (zetaold - thetatildeold * tautildeold) / rhotildeold
        taud = (zeta - thetatilde * tautildeold) / rhodold
        d = d + betacheck * betacheck
        normr = sqrt(d + (betad - taud)**2 + betadd * betadd)

        # Estimate ||A||.
        normA2 = normA2 + beta * beta
        normA = sqrt(normA2)
        normA2 = normA2 + alpha * alpha

        # Estimate cond(A).
        maxrbar = max(maxrbar, rhobarold)
        if itn > 1:
            minrbar = min(minrbar, rhobarold)
        condA = max(maxrbar, rhotemp) / min(minrbar, rhotemp)

        # Test for convergence.

        # Compute norms for convergence testing.
        normar = np.abs(zetabar)
        normx = norm(x)

        # Now use these norms to estimate certain other quantities,
        # some of which will be small near a solution.
        test1 = normr / normb
        if (normA * normr) != 0:
            test2 = normar / (normA * normr)
        else:
            test2 = inf
        test3 = 1 / condA
        t1 = test1 / (1 + normA * normx / normb)
        rtol = btol + atol * normA * normx / normb

        # The following tests guard against extremely small values of
        # atol, btol or ctol.  (The user may have set any or all of
        # the parameters atol, btol to 0.)
        # The effect is equivalent to the normAl tests using
        # atol = eps,  btol = eps.
        if itn >= maxiter:
            istop = 7
        if 1 + test3 <= 1:
            istop = 6
        if 1 + test2 <= 1:
            istop = 5
        if 1 + t1 <= 1:
            istop = 4

        # Allow for tolerances set by the user.
        if test3 <= ctol:
            istop = 3
        if test2 <= atol:
            istop = 2
        if test1 <= rtol:
            istop = 1

        if istop > 0:
            break

    return x, grad, itn, normr


def sym_ortho(a, b):
    """
    Stable implementation of Givens rotation.
    
    Notes
    -----
    The routine 'SymOrtho' was added for numerical stability. This is
    recommended by S.-C. Choi in [1]_.  It removes the unpleasant potential of
    ``1/eps`` in some important places (see, for example text following
    "Compute the next plane rotation Qk" in minres.py). This function is useful
    for the LSMR function.
    
    References
    ----------
    .. [1] S.-C. Choi, "Iterative Methods for Singular Linear Equations
           and Least-Squares Problems", Dissertation,
           http://www.stanford.edu/group/SOL/dissertations/sou-cheng-choi-thesis.pdf
    """
    
    if b == 0:
        return np.sign(a), 0, np.abs(a)
    elif a == 0:
        return 0, np.sign(b), np.abs(b)
    elif np.abs(b) > np.abs(a):
        tau = a / b
        s = np.sign(b) / np.sqrt(1 + tau * tau)
        c = s * tau
        r = b / s
    else:
        tau = b / a
        c = np.sign(a) / np.sqrt(1+tau*tau)
        s = c * tau
        r = a / c
    return c, s, r


@njit(nogil=True, parallel=True)
def residual(res, T, T_aux, m, n, p):
    """
    This function computes (updates) the residuals between a 3-D tensor T in R^m⊗R^n⊗R^p and an approximation T_approx of 
    rank r. The tensor T_approx is of the form T_approx = X_1⊗Y_1⊗Z_1 + ... + X_r⊗Y_r⊗Z_r, where
    X = [X_1, ..., X_r],
    Y = [Y_1, ..., Y_r],
    Z = [Z_1, ..., Z_r].
    
    The 'residual map' is a map res:R^{r+r(m+n+p)}->R^{m*n*p}. For each i,j,k=0...n, the residual r_{i,j,k} is given by 
    res_{i,j,k} = T_{i,j,k} - sum_{l=1}^r X_{il}*Y_{jl}*Z_{kl}.
    
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
    for i in prange(m):
        for j in range(n):
            for k in range(p):
                s = n*p*i + p*j + k
                res[s] = T[i,j,k] - T_aux[i,j,k]
                            
    return res


@njit(nogil=True)
def residual_entries(T_ijk, X, Y, Z, r, i, j, k):
    """ 
    Computation of each individual residual in the residual function. 
    """
    
    acc = 0.0
    for l in range(r):
        acc += X[i,l]*Y[j,l]*Z[k,l]    
    
    res_ijk = T_ijk - acc
        
    return res_ijk


def update_damp(damp, old_error, error, residualnorm):
    """ 
    Update rule of the damping parameter for the dGN function. 
    """
    
    gain_ratio = 2*(old_error - error)/(old_error - residualnorm)
        
    if gain_ratio < 0.75:
        damp = damp/2
    elif gain_ratio > 0.9:
        damp = 1.5*damp
    
    return damp


def cg(X, Y, Z, data, data_rmatvec, y, grad, b, m, n, p, r, damp, maxiter, tol):
    """
    Conjugate gradient algorithm specialized to the tensor case.
    """

    maxiter = min(maxiter, r*(m+n+p))
    
    # Give names to the arrays.
    Gr_X, Gr_Y, Gr_Z, Gr_XY, Gr_XZ, Gr_YZ, V_Xt, V_Yt, V_Zt, V_Xt_dot_X, V_Yt_dot_Y, V_Zt_dot_Z, Gr_Z_V_Yt_dot_Y, Gr_Y_V_Zt_dot_Z, Gr_X_V_Zt_dot_Z, Gr_Z_V_Xt_dot_X, Gr_Y_V_Xt_dot_X, Gr_X_V_Yt_dot_Y, X_dot_Gr_Z_V_Yt_dot_Y, X_dot_Gr_Y_V_Zt_dot_Z, Y_dot_Gr_X_V_Zt_dot_Z, Y_dot_Gr_Z_V_Xt_dot_X, Z_dot_Gr_Y_V_Xt_dot_X, Z_dot_Gr_X_V_Yt_dot_Y, Gr_YZ_V_Xt, Gr_XZ_V_Yt, Gr_XY_V_Zt, B_X_v, B_Y_v, B_Z_v, B_XY_v, B_XZ_v, B_YZ_v, B_XYt_v, B_XZt_v, B_YZt_v, X_norms, Y_norms, Z_norms, gamma_X, gamma_Y, gamma_Z, Gamma, M, L, residual_cg, P, Q, z = data
    M_X, M_Y, M_Z, w_Xt, Bu_Xt, w_Yt, Bu_Yt, w_Zt, Bu_Zt = data_rmatvec
    
    # Compute the values of all arrays.
    Gr_X, Gr_Y, Gr_Z, Gr_XY, Gr_XZ, Gr_YZ = gramians(X, Y, Z, Gr_X, Gr_Y, Gr_Z, Gr_XY, Gr_XZ, Gr_YZ)
    M_X, M_Y, M_Z = update_data_rmatvec(X, Y, Z, M_X, M_Y, M_Z)
    L = regularization(X, Y, Z, X_norms, Y_norms, Z_norms, gamma_X, gamma_Y, gamma_Z, Gamma, m, n, p, r)
    M = precond(X, Y, Z, L, M, damp, m, n, p, r)
    const = 2 + int(maxiter/5)
    
    y = 0*y
    
    # grad = Dres^T*res is the gradient of the error function E.    
    grad = rmatvec(b, w_Xt, Bu_Xt, M_X, w_Yt, Bu_Yt, M_Y, w_Zt, Bu_Zt, M_Z, m, n, p, r)
    residual = M*grad
    P = residual
    residualnorm = dot(residual, residual)
    if residualnorm == 0.0:
        residualnorm = 1e-6
    residualnorm_new = 0.0
    alpha = 0.0
    beta = 0.0
    residualnorm_list = []
       
    for itn in range(maxiter):
        Q = M*P
        z = matvec(X, Y, Z, Gr_X, Gr_Y, Gr_Z, Gr_XY, Gr_XZ, Gr_YZ, V_Xt, V_Yt, V_Zt, V_Xt_dot_X, V_Yt_dot_Y, V_Zt_dot_Z, Gr_Z_V_Yt_dot_Y, Gr_Y_V_Zt_dot_Z, Gr_X_V_Zt_dot_Z, Gr_Z_V_Xt_dot_X, Gr_Y_V_Xt_dot_X, Gr_X_V_Yt_dot_Y, X_dot_Gr_Z_V_Yt_dot_Y, X_dot_Gr_Y_V_Zt_dot_Z, Y_dot_Gr_X_V_Zt_dot_Z, Y_dot_Gr_Z_V_Xt_dot_X, Z_dot_Gr_Y_V_Xt_dot_X, Z_dot_Gr_X_V_Yt_dot_Y, Gr_YZ_V_Xt, Gr_XZ_V_Yt, Gr_XY_V_Zt, B_X_v, B_Y_v, B_Z_v, B_XY_v, B_XZ_v, B_YZ_v, B_XYt_v, B_XZt_v, B_YZt_v, Q, m, n, p, r) + damp*L*Q
        z = M*z
        denominator = dot(P.T, z)
        if denominator == 0.0:
            denominator = 1e-6
        alpha = residualnorm/denominator
        y += alpha*P
        residual -= alpha*z
        residualnorm_new = dot(residual, residual)
        beta = residualnorm_new/residualnorm
        residualnorm = residualnorm_new
        residualnorm_list.append(residualnorm)
        P = residual + beta*P

        # Stopping criteria.
        if residualnorm < tol:
            break   

        # Stop if the average residual norms from itn-2*const to itn-const is less than the average of residual norms from itn-const to itn.
        if itn >= 2*const and itn%const == 0:  
            if mean(residualnorm_list[itn-2*const : itn-const]) < mean(residualnorm_list[itn-const : itn]):
                break
    
    return M*y, grad, itn+1, residualnorm


def prepare_data(m, n, p, r):
    """
    Initialize all necessary matrices to keep the values of several computations during the program.
    """

    # Gramians
    Gr_X = empty((r,r), dtype = float64)
    Gr_Y = empty((r,r), dtype = float64)
    Gr_Z = empty((r,r), dtype = float64)
    Gr_XY = empty((r,r), dtype = float64)
    Gr_XZ = empty((r,r), dtype = float64)
    Gr_YZ = empty((r,r), dtype = float64)
    
    # V_X^T, V_Y^T, V_Z^T
    V_Xt = empty((r,m), dtype = float64)
    V_Yt = empty((r,n), dtype = float64)
    V_Zt = empty((r,p), dtype = float64)

    # Initializations of matrices to receive the results of the computations.
    V_Xt_dot_X = empty((r,r), dtype = float64)
    V_Yt_dot_Y = empty((r,r), dtype = float64)
    V_Zt_dot_Z = empty((r,r), dtype = float64)
    Gr_Z_V_Yt_dot_Y = empty((r,r), dtype = float64)
    Gr_Y_V_Zt_dot_Z = empty((r,r), dtype = float64)
    Gr_X_V_Zt_dot_Z = empty((r,r), dtype = float64)
    Gr_Z_V_Xt_dot_X = empty((r,r), dtype = float64)
    Gr_Y_V_Xt_dot_X = empty((r,r), dtype = float64)
    Gr_X_V_Yt_dot_Y = empty((r,r), dtype = float64)    
    X_dot_Gr_Z_V_Yt_dot_Y = empty((r,r), dtype = float64)
    X_dot_Gr_Y_V_Zt_dot_Z = empty((r,r), dtype = float64)
    Y_dot_Gr_X_V_Zt_dot_Z = empty((r,r), dtype = float64)
    Y_dot_Gr_Z_V_Xt_dot_X = empty((r,r), dtype = float64)
    Z_dot_Gr_Y_V_Xt_dot_X = empty((r,r), dtype = float64)
    Z_dot_Gr_X_V_Yt_dot_Y = empty((r,r), dtype = float64)
    
    # Matrices for the diagonal block
    Gr_YZ_V_Xt = empty((m,r), dtype = float64)
    Gr_XZ_V_Yt = empty((n,r), dtype = float64)
    Gr_XY_V_Zt = empty((p,r), dtype = float64)
    
    # Final blocks
    B_X_v = empty(m*r, dtype = float64)
    B_Y_v = empty(n*r, dtype = float64)
    B_Z_v = empty(p*r, dtype = float64)
    B_XY_v = empty(m*r, dtype = float64)
    B_XZ_v = empty(m*r, dtype = float64)
    B_YZ_v = empty(n*r, dtype = float64)
    B_XYt_v = empty(n*r, dtype = float64)
    B_XZt_v = empty(p*r, dtype = float64) 
    B_YZt_v = empty(p*r, dtype = float64)

    # Matrices to use when constructing the Tikhonov matrix for regularization.
    X_norms = empty(r, dtype = float64)
    Y_norms = empty(r, dtype = float64)
    Z_norms = empty(r, dtype = float64)
    gamma_X = empty(r, dtype = float64)
    gamma_Y = empty(r, dtype = float64)
    gamma_Z = empty(r, dtype = float64)
    Gamma = empty(r*(m+n+p), dtype = float64)

    # Arrays to be used in the Conjugated Gradient.
    M = ones(r*(m+n+p), dtype = float64)
    L = ones(r*(m+n+p), dtype = float64)    
    residual_cg = empty(r*(m+n+p), dtype = float64)
    P = empty(r*(m+n+p), dtype = float64)
    Q = empty(r*(m+n+p), dtype = float64)
    z = empty(r*(m+n+p), dtype = float64)
    
    return Gr_X, Gr_Y, Gr_Z, Gr_XY, Gr_XZ, Gr_YZ, V_Xt, V_Yt, V_Zt, V_Xt_dot_X, V_Yt_dot_Y, V_Zt_dot_Z, Gr_Z_V_Yt_dot_Y, Gr_Y_V_Zt_dot_Z, Gr_X_V_Zt_dot_Z, Gr_Z_V_Xt_dot_X, Gr_Y_V_Xt_dot_X, Gr_X_V_Yt_dot_Y, X_dot_Gr_Z_V_Yt_dot_Y, X_dot_Gr_Y_V_Zt_dot_Z, Y_dot_Gr_X_V_Zt_dot_Z, Y_dot_Gr_Z_V_Xt_dot_X, Z_dot_Gr_Y_V_Xt_dot_X, Z_dot_Gr_X_V_Yt_dot_Y, Gr_YZ_V_Xt, Gr_XZ_V_Yt, Gr_XY_V_Zt, B_X_v, B_Y_v, B_Z_v, B_XY_v, B_XZ_v, B_YZ_v, B_XYt_v, B_XZt_v, B_YZt_v, X_norms, Y_norms, Z_norms, gamma_X, gamma_Y, gamma_Z, Gamma, M, L, residual_cg, P, Q, z   


def prepare_data_rmatvec(m, n, p, r):
    """
    This function creates several auxiliar matrices which will be used later to accelerate matrix-vector products.
    """

    M_X = empty((n*p, r), dtype = float64)    
    M_Y = empty((m*p, r), dtype = float64)
    M_Z = empty((m*n,r), dtype = float64) 
    
    # B_X^T
    w_Xt = empty(n*p, dtype = float64)
    Bu_Xt = empty(r*m, dtype = float64) 
    
    # B_Y^T
    w_Yt = empty(m*p, dtype = float64)
    Bu_Yt = empty(r*n, dtype = float64) 
    
    # B_Z^T
    w_Zt = empty((p,m*n), dtype = float64)
    Bu_Zt = empty(r*p, dtype = float64)
        
    return M_X, M_Y, M_Z, w_Xt, Bu_Xt, w_Yt, Bu_Yt, w_Zt, Bu_Zt


def update_data_rmatvec(X, Y, Z, M_X, M_Y, M_Z):
    """
    This function creates several auxiliar matrices which will be used later to accelerate matrix-vector products.
    """
    M_X = -mlinalg.khatri_rao(Y, Z)
    M_Y = -mlinalg.khatri_rao(X, Z)
    M_Z = -mlinalg.khatri_rao(X, Y) 
        
    return M_X, M_Y, M_Z


@njit(nogil=True)
def gramians(X, Y, Z, Gr_X, Gr_Y, Gr_Z, Gr_XY, Gr_XZ, Gr_YZ):
    """ 
    Computes all Gramians matrices of X, Y, Z. Also it computes all Hadamard products between the different Gramians. 
    """
    
    Gr_X = dot(X.T, X)
    Gr_Y = dot(Y.T, Y)
    Gr_Z = dot(Z.T, Z)
    Gr_XY = Gr_X*Gr_Y
    Gr_XZ = Gr_X*Gr_Z
    Gr_YZ = Gr_Y*Gr_Z
            
    return Gr_X, Gr_Y, Gr_Z, Gr_XY, Gr_XZ, Gr_YZ


@njit(nogil=True)
def matvec(X, Y, Z, Gr_X, Gr_Y, Gr_Z, Gr_XY, Gr_XZ, Gr_YZ, V_Xt, V_Yt, V_Zt, V_Xt_dot_X, V_Yt_dot_Y, V_Zt_dot_Z, Gr_Z_V_Yt_dot_Y, Gr_Y_V_Zt_dot_Z, Gr_X_V_Zt_dot_Z, Gr_Z_V_Xt_dot_X, Gr_Y_V_Xt_dot_X, Gr_X_V_Yt_dot_Y, X_dot_Gr_Z_V_Yt_dot_Y, X_dot_Gr_Y_V_Zt_dot_Z, Y_dot_Gr_X_V_Zt_dot_Z, Y_dot_Gr_Z_V_Xt_dot_X, Z_dot_Gr_Y_V_Xt_dot_X, Z_dot_Gr_X_V_Yt_dot_Y, Gr_YZ_V_Xt, Gr_XZ_V_Yt, Gr_XY_V_Zt, B_X_v, B_Y_v, B_Z_v, B_XY_v, B_XZ_v, B_YZ_v, B_XYt_v, B_XZt_v, B_YZt_v, v, m, n, p, r): 
    """
    Makes the matrix-vector computation (Dres.transpose*Dres)*v. 
    """
     
    # Split v into three blocks, convert them into matrices and transpose them. 
    # With this we have the matrices V_X^T, V_Y^T, V_Z^T.
    V_Xt = v[0 : m*r].reshape(r, m)
    V_Yt = v[m*r : r*(m+n)].reshape(r, n)
    V_Zt = v[r*(m+n) : r*(m+n+p)].reshape(r, p)
       
    # Compute the products V_X^T*X, V_Y^T*Y, V_Z^T*Z
    V_Xt_dot_X = dot(V_Xt, X)
    V_Yt_dot_Y = dot(V_Yt, Y)
    V_Zt_dot_Z = dot(V_Zt, Z)
    
    # Compute the Hadamard products
    Gr_Z_V_Yt_dot_Y = mlinalg.hadamard(Gr_Z, V_Yt_dot_Y, Gr_Z_V_Yt_dot_Y, r)
    Gr_Y_V_Zt_dot_Z = mlinalg.hadamard(Gr_Y, V_Zt_dot_Z, Gr_Y_V_Zt_dot_Z, r)
    Gr_X_V_Zt_dot_Z = mlinalg.hadamard(Gr_X, V_Zt_dot_Z, Gr_X_V_Zt_dot_Z, r)
    Gr_Z_V_Xt_dot_X = mlinalg.hadamard(Gr_Z, V_Xt_dot_X, Gr_Z_V_Xt_dot_X, r)
    Gr_Y_V_Xt_dot_X = mlinalg.hadamard(Gr_Y, V_Xt_dot_X, Gr_Y_V_Xt_dot_X, r)
    Gr_X_V_Yt_dot_Y = mlinalg.hadamard(Gr_X, V_Yt_dot_Y, Gr_X_V_Yt_dot_Y, r)
    
    # Compute the final products
    X_dot_Gr_Z_V_Yt_dot_Y = dot(X, Gr_Z_V_Yt_dot_Y)
    X_dot_Gr_Y_V_Zt_dot_Z = dot(X, Gr_Y_V_Zt_dot_Z)
    Y_dot_Gr_X_V_Zt_dot_Z = dot(Y, Gr_X_V_Zt_dot_Z)
    Y_dot_Gr_Z_V_Xt_dot_X = dot(Y, Gr_Z_V_Xt_dot_X)
    Z_dot_Gr_Y_V_Xt_dot_X = dot(Z, Gr_Y_V_Xt_dot_X)
    Z_dot_Gr_X_V_Yt_dot_Y = dot(Z, Gr_X_V_Yt_dot_Y)
    
    # Diagonal block matrices
    Gr_YZ_V_Xt = dot(Gr_YZ, V_Xt)
    Gr_XZ_V_Yt = dot(Gr_XZ, V_Yt)
    Gr_XY_V_Zt = dot(Gr_XY, V_Zt)
    
    # Vectorize the matrices to have the final vectors
    B_X_v = cnv.vect(Gr_YZ_V_Xt, B_X_v, m, r)
    B_Y_v = cnv.vect(Gr_XZ_V_Yt, B_Y_v, n, r)
    B_Z_v = cnv.vect(Gr_XY_V_Zt, B_Z_v, p, r)
    B_XY_v = cnv.vec(X_dot_Gr_Z_V_Yt_dot_Y, B_XY_v, m, r)
    B_XZ_v = cnv.vec(X_dot_Gr_Y_V_Zt_dot_Z, B_XZ_v, m, r)
    B_YZ_v = cnv.vec(Y_dot_Gr_X_V_Zt_dot_Z, B_YZ_v, n, r)
    B_XYt_v = cnv.vec(Y_dot_Gr_Z_V_Xt_dot_X, B_XYt_v, n, r)
    B_XZt_v = cnv.vec(Z_dot_Gr_Y_V_Xt_dot_X, B_XZt_v, p, r) 
    B_YZt_v = cnv.vec(Z_dot_Gr_X_V_Yt_dot_Y, B_YZt_v, p, r)

    return concatenate((B_X_v + B_XY_v + B_XZ_v, B_XYt_v + B_Y_v + B_YZ_v, B_XZt_v + B_YZt_v + B_Z_v)) 


def lsmr_prepare_data(X, Y, Z, m, n, p, r):
    """
    This function creates several auxiliar matrices which will be used later 
    to accelerate matrix-vector products.
    """

    "B_X"
    w_X = empty(r, dtype = np.float64)
    Bv_X = empty(m*n*p, dtype = np.float64) 
    M_X = empty((n*p, r), dtype = np.float64)

    "B_Y"
    w_Y = empty(r, dtype = np.float64)
    Mw_Y = empty(m*p, dtype = np.float64) 
    Bv_Y = empty(m*n*p, dtype = np.float64)
    M_Y = empty((m*p, r), dtype = np.float64)

    "B_Z"
    w_Z = empty(p*r, dtype = np.float64)
    Bv_Z = empty(m*n*p, dtype = np.float64)
    M_Z = empty((m*n,r), dtype = np.float64) 

    "B_X^T"
    w_Xt = empty(n*p, dtype = np.float64)
    Bu_Xt = empty(r*m, dtype = np.float64) 
    
    "B_Y^T"
    w_Yt = empty(m*p, dtype = np.float64)
    Bu_Yt = empty(r*n, dtype = np.float64) 
    
    "B_Z^T"
    w_Zt = empty((p,m*n), dtype = np.float64)
    Bu_Zt = empty(r*p, dtype = np.float64) 
           
    return w_X, Bv_X, M_X, w_Y, Mw_Y, Bv_Y, M_Y, w_Z, Bv_Z, M_Z, w_Xt, Bu_Xt, w_Yt, Bu_Yt, w_Zt, Bu_Zt


@njit(nogil=True)
def lsmr_matvec(X, Y, v, w_X, Bv_X, M_X, w_Y, Mw_Y, Bv_Y, M_Y, w_Z, Bv_Z, M_Z, m, n, p, r):  
    """    
    Computes the matrix-vector product Dres*v.
    """

    values = arange(r)
    values1 = arange(m*n)

    "B_X"
    for i in range(m):
        w_X = v[i + m*values] 
        Bv_X[i*n*p : (i+1)*n*p] = dot(M_X, w_X)

    "B_Y"
    for j in range(n):
        w_Y = v[m*r + j + n*values] 
        Mw_Y = dot(M_Y, w_Y)
        for i in range(m):
            Bv_Y[j*p + i*n*p : (j+1)*p + i*n*p] = Mw_Y[i*p : (i+1)*p]

    "B_Z"
    w_Z = v[r*(m+n):]
    w_Z = w_Z.reshape(r, p).T
    for k in range(p):
        Bv_Z[k + p*values1] = dot(M_Z, w_Z[k,:])

    return Bv_X + Bv_Y + Bv_Z


@njit(nogil=True)
def rmatvec(u, w_Xt, Bu_Xt, M_X, w_Yt, Bu_Yt, M_Y, w_Zt, Bu_Zt, M_Z, m, n, p, r):   
    """    
    Computes the matrix-vector product Dres.transpose*u.
    """

    values = arange(r)
 
    "B_Xt"
    for i in range(m):
        w_Xt = u[i*n*p : (i+1)*n*p] 
        idx = i + m*values
        Bu_Xt[idx] = np.dot(w_Xt, M_X)

    "B_Yt"
    for j in range(n):
        for i in range(m):
            w_Yt[i*p : (i+1)*p] = u[j*p + i*n*p : (j+1)*p + i*n*p] 
        idx = j + n*values
        Bu_Yt[idx] = np.dot(w_Yt, M_Y)
        
    "B_Zt"
    w_Zt = u.reshape(m*n, p).T
    for k in range(p):
        idx = k + p*values
        Bu_Zt[idx] = np.dot(w_Zt[k,:], M_Z)

    return hstack((Bu_Xt, Bu_Yt, Bu_Zt))


@njit(nogil=True)
def regularization(X, Y, Z, X_norms, Y_norms, Z_norms, gamma_X, gamma_Y, gamma_Z, Gamma, m, n, p, r):
    """
    Computes the Tikhonov matrix Gamma, where Gamma is a diagonal matrix designed specifically to make 
    Dres.transpose*Dres + Gamma diagonally dominant.
    """
        
    for l in range(0, r):
        X_norms[l] = sqrt( dot(X[:,l], X[:,l]) )
        Y_norms[l] = sqrt( dot(Y[:,l], Y[:,l]) )
        Z_norms[l] = sqrt( dot(Z[:,l], Z[:,l]) )
    
    max_XY = np.max(X_norms*Y_norms)
    max_XZ = np.max(X_norms*Z_norms)
    max_YZ = np.max(Y_norms*Z_norms)
    max_all = max(max_XY, max_XZ, max_YZ)
        
    for l in range(0, r):
        gamma_X[l] = Y_norms[l]*Z_norms[l]*max_all
        gamma_Y[l] = X_norms[l]*Z_norms[l]*max_all
        gamma_Z[l] = X_norms[l]*Y_norms[l]*max_all
        
    for l in range(0, r):
        Gamma[l*m : (l+1)*m] = gamma_X[l]
        Gamma[m*r+l*n : m*r+(l+1)*n] = gamma_Y[l]
        Gamma[r*(m+n)+l*p : r*(m+n)+(l+1)*p] = gamma_Z[l]
        
    return Gamma


@njit(nogil=True)
def precond(X, Y, Z, L, M, damp, m, n, p, r):
    """
    This function constructs a preconditioner in order to accelerate the Conjugate Gradient fucntion. It is a diagonal 
    preconditioner designed to make Dres.transpose*Dres + Gamma a unit diagonal matrix. Since the matrix is diagonally 
    dominant, the result will be close to the identity matrix. Therefore, it will have its eigenvalues clustered together.
    """
    for l in range(0, r):
        M[l*m : (l+1)*m] = dot(Y[:,l], Y[:,l])*dot(Z[:,l], Z[:,l]) + damp*L[l*m : (l+1)*m] 
        M[m*r+l*n : m*r+(l+1)*n] = dot(X[:,l], X[:,l])*dot(Z[:,l], Z[:,l]) + damp*L[m*r+l*n : m*r+(l+1)*n] 
        M[r*(m+n)+l*p : r*(m+n)+(l+1)*p] = dot(X[:,l], X[:,l])*dot(Y[:,l], Y[:,l]) + damp*L[r*(m+n)+l*p : r*(m+n)+(l+1)*p]    
        
    M = 1/sqrt(M)
    return M