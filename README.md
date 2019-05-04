# Tensor Fox

Tensor Fox is a high performance package of multilinear algebra and tensor routines, with focus on the Canonical Polyadic Decomposition (CPD).

## Table of Contents
* :fox_face:  [Motivation](#motivation)
* :fox_face:  [Getting Started](#getting-started)
* :fox_face:  [Performance](#performance)
* :fox_face:  [Structure of Tensor Fox](#structure-of-tensor-fox)
* :fox_face:  [Author](#author)
* :fox_face:  [License](#license)
* :fox_face:  [References](#references)

## :fox_face: Motivation

Multidimensional data structures are common these days, and to extract useful information from them is crucial for several applications. For bidimensional data structures (i.e., matrices), one can rely in decompositions such as the [Singular Value Decomposition](https://en.wikipedia.org/wiki/Singular_value_decomposition) (SVD) for instance. There are two  possible generalizations of the SVD for multidimensional arrays of higher order: the *multilinear singular value decomposition* (MLSVD) and the *canonical polyadic decomposition* (CPD). The former can be seen as a [PCA](https://en.wikipedia.org/wiki/Principal_component_analysis) of higher order and is useful for dimensionality reduction, whereas the latter is useful to detect latent variables. Computing the MLSVD is just a matter of computing several SVD's, but the CPD is a challenging problem.

![alt text](https://github.com/felipebottega/Tensor-Fox/blob/master/readme_files/tensor-intuition.png)

Consider a tensor and a value which is expected to be the [rank](https://en.wikipedia.org/wiki/Tensor_rank_decomposition#Tensor_rank) of the tensor. The determination of the actual rank is a NP-hard problem, so the best option is to rely on heuristics, guessing and estimatse. Although the value of the rank is a hard task, once we have its value or a reasonable estimate, computing an approximated CPD is a polynomial task. There are several implementations of algorithms to compute a CPD, but most of them relies on the *alternating least squares* (ALS) algorithm, which is cheap to compute but has severe convergence issues. Algorithms like the *damped Gauss-Newton* (dGN) are more robust but in general are much more costly. Tensor Fox is a CPD solver for Python (with Numpy and Numba as backend) which manages to use the dGN algorithm in a cheap way, being robust while also being competitive with ALS in terms of speed. Furthermore, Tensor Fox offers several additional multilinear algebra routines in the context of tensors. 

## :fox_face: Getting Started

In order to have everything working properly, all files of Tensor Fox must be in the same folder of your program. At the moment we are only offering the module files, so there is no install procedure to follow, just download the modules and import them locally. To be able to use Tensor Fox properly you will need the following packages already installed on your computer:

    numpy
    pandas
    scipy
    sklearn
    matplotlib
    numba

Make sure Numba and Numpy updated. Additionaly, make sure you are using a nice version of BLAS. That is all! Tensor Fox is read to go! 

Let's start importing Tensor Fox and other necessary modules for now.

![alt text](https://github.com/felipebottega/Tensor-Fox/blob/master/readme_files/ipynb1.png)

### Creating Tensors and Getting Information 

Let's create a little tensor **T** just to see how Tensor Fox works at its basics. For third order tensors (3D arrays) I use the convention that **T**[ijk] refers to the *i*-th row, *j*-column and *k*-slice (frontal slice) of **T**. For instance, consider the tensor defined above (the frontal slices of **T** are showed).

![alt_text](https://github.com/felipebottega/Tensor-Fox/blob/master/readme_files/formula1.png)

Since Numpy's convention is different from ours with regard to third order tensors. This convention may be irrelevant when using the routines of Tensor Fox, but since I build all the modules thinking this way, it is fair that this point is made explicitly. The function **showtens** prints a third order tensor with this particular convention and print tensors of higher order just as Numpy would print. Below we show both conventions with an example of third order tensor. 

![alt_text](https://github.com/felipebottega/Tensor-Fox/blob/master/readme_files/ipynb2.png)

### Computing the CPD

Now let's turn to the most important tool of Tensor Fox, the computation of the CPD. We can compute the corresponding CPD with simply calling the function **cpd** with the tensor and the rank as arguments. This is just the tip of the iceberg of Tensor Fox, to know more check out the [tutorial](https://github.com/felipebottega/Tensor-Fox/tree/master/tutorial) and the [examples of applications](https://github.com/felipebottega/Tensor-Fox/tree/master/examples). 

![alt_text](https://github.com/felipebottega/Tensor-Fox/blob/master/readme_files/ipynb3.png)

## :fox_face: Performance

In the following we compare the performances of Tensor Fox and other known tensor packages: Tensorlab, Tensor Toolbox and Tensorly. Our first benchmark consists in measuring the effort for the other solvers to obtain a solution close to the Tensor Fox default. We compute the CPD of four fixed tensors:

 * *Swimmer tensor*: 

## :fox_face: Structure of Tensor Fox

In this section we summarize all the features Tensor Fox has to offer. As already mentioned, computing the CPD is the main goal of Tensor Fox, but in order to accomplish this mission several 'sub-goals' had to be overcome first. Many of these sub-goals ended up being important routines of multilinear algebra. Besides that, during the development of this project several convenience routines were added, such as statistics analysis of tensors, rank estimation, automated plotting with CPD information, and many more. Below we present the modules of Tensor Fox and gives a brief description of their main functions.

|**TensorFox**|  |
|---|---|
| cpd| computes the CPD of a tensor **T** with rank *R*. |
| rank| estimates the rank of a tensor.|
| stats| given a tensor **T** and a rank *R*, this fucntions computes some statistics regarding the CPD computation. |
| foxit| does the same job as the *cpd* function but at the end it prints and plots relevant information. |
   
|**Auxiliar**|  |
|---|---|
| tens2matlab| given a tensor, this function creates a Matlab file containing the tensor and its dimensions. |
| sort_dims| given a tensor, this function sort its dimensions in descending order and returns the sorted tensor. |
| rank1| given the factors of a CPD, this function converts them into a matrix, which is the first frontal slice of the tensor in coordinates obtained by this rank-1 term. |
   
| **Compression**|  |
|---|---|
| mlsvd| computes the MLSVD of a tensor. |
| clean_compression| truncates the MLSVD. |
   
| **Conversion**|  |
|---|---|
| cpd2tens| converts the factor matrices to tensor in coordinate format. |
| unfold| given a tensor and a choice of a mode, this function computes the unfolding of the tensor with respect of that mode.  |
| foldback| given a matrix representing a unfolding of some mode and the dimensions of the original tensor, this function retrieves the original tensor from its unfolding. |
| normalize| normalize the columns of the factors to have unit column norm and introduce a central tensor with the scaling factors. |
| denormalize| given the normalized factors together with a central tensor, this function retrives the non-normalized factors. |
| equalize| make the vectors of each mode to have the same norm. |
   
| **Critical**| |
|---|---|
|   | this module responsible for the most costly parts of Tensor Fox (basically it is a module of boring loops) |

| **Display**|  |
|---|---|
| infotens| display several informations about a given tensor. |
| test_tensors| a function made specifically to test different models against different tensors. It is very useful when one is facing difficult tensors and needs to tune the parameters accordingly. |
   
| **GaussNewton**|   |
|---|---|
| dGN| [damped Gauss-Newton](https://en.wikipedia.org/wiki/Gauss%E2%80%93Newton_algorithm) function adapated for the tensor problem.. |
| cg| [conjugate gradient](https://en.wikipedia.org/wiki/Conjugate_gradient_method) function specifically made for the tensor problem. |
| lsmr| [LSMR](http://web.stanford.edu/group/SOL/software/lsmr/) function adapated for the tensor problem. |
| regularization| computes the [Tikhonov matrix](https://en.wikipedia.org/wiki/Tikhonov_regularization) for the inner algorithm. |
| precond| computes the [preconditioner matrix](https://en.wikipedia.org/wiki/Preconditioner) for the inner algorithm.  |
   
| **Initialization**|  |
|---|---|
| starting_point| main function to generates the starting point. There are four possible methods of initialization, 'random', 'smart_random', 'smart', or you can provide your own starting point. |
| find_factor| if the user introduce constraints to the entries of the solution, a projection is made at each step of the dGN. This projection is based on three parameters, where the least clear is the *factor* parameter. This function helps the user to find the best factor for the starting point. For more information, see this notebook. |
   
| **MultilinearAlgebra**| |
|---|---|
| multilin_mult| performs the multilinear multiplication. |
| multirank_approx| given a tensor **T** and a prescribed multirank (R1, ..., Rm), this function tries to find the (almost) best approximation of **T** with multirank (R1, ..., Rm). |
| kronecker| computes the [Kronecker product](https://en.wikipedia.org/wiki/Kronecker_product) between two matrices. |
| khatri_rao| computes the [Khatri-Rao product](https://en.wikipedia.org/wiki/Kronecker_product#Khatri%E2%80%93Rao_product) between two matrices. |
| hadamard| computes the [Hadamar product](https://en.wikipedia.org/wiki/Hadamard_product_(matrices)) between two matrices. |

## Author

* Felipe B. Diniz: https://github.com/felipebottega
* Contact email: felipebottega@gmail.com
* Linkedin: https://www.linkedin.com/in/felipe-diniz-4a212163/?locale=en_US
* Kaggle: https://www.kaggle.com/felipebottega

## License

This project is licensed under the GNU GENERAL PUBLIC LICENSE - see the [LICENSE.md](https://github.com/felipebottega/Tensor-Fox/blob/master/LICENSE) file for details.
    

## References:

 * P. Comon, X. Luciani, and A. L. F. de Almeida, *Tensor Decompositions, Alternating Least Squares and other Tales*, Journal of Chemometrics, Wiley, 2009.   
 * T. G. Kolda and B. W. Bader, *Tensor Decompositions and Applications*, SIAM Review, 51:3, in press (2009).   
 * J. M. Landsberg, *Tensors: Geometry and Applications*, AMS, Providence, RI, 2012.   
 * B. Savas, and Lars Eldén, *Handwritten Digit Classification Using Higher Order Singular Value Decomposition*, Pattern Recognition Society, vol. 40, no. 3, pp. 993-1003, 2007.
 * C. J. Hillar, and L.-H. Lim. *Most tensor problems are NP-hard*, Journal of the ACM, 60(6):45:1-45:39, November 2013. ISSN 0004-5411. doi: 10.1145/2512329.
 * A. Shashua, and T. Hazan, *Non-negative Tensor Factorization with Applications to Statistics and Computer Vision*, Proceedings of the 22nd International Conference on Machine Learning (ICML), 22 (2005), pp. 792-799.
 * S. Rabanser, O. Shchur, and S. Günnemann, *Introduction to Tensor Decompositions and their Applications in Machine Learning*, arXiv:1711.10781v1 (2017). 
 * A. H. Phan, P. Tichavsky, and A. Cichoki, *Low Complexity Damped Gauss-Newton Algorithm for CANDECOMP/PARAFAC*, SIAM Journal on Matrix Analysis and Applications, 34 (1), 126-147 (2013).
 * L. De Lathauwer, B. De Moor, and J. Vandewalle, *A Multilinear Singular Value Decomposition*, SIAM J. Matrix Anal. Appl., 21 (2000), pp. 1253-1278.
 * https://www.tensorlab.net/
 * http://www.sandia.gov/~tgkolda/TensorToolbox/
 * https://github.com/tensorly/
