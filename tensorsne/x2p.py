import numpy as np
import scipy as sp

from ._cpp import BH_SNE
from .knn import knn


def x2p(X, perplexity=50, method='exact', approx_method='vptree',
        verbose=False):

    assert method in ('exact', 'knn', 'approx'), 'Invalid method'

    # zero mean
    X = (X - X.mean(axis=0))

    if method == 'exact':
        assert isinstance(X, np.ndarray), 'Exact method requires dense array'
        P = BH_SNE().computeGaussianPerplexityExact(X, perplexity)
    elif method == 'knn':
        assert isinstance(X, np.ndarray), 'knn method requires dense array'
        P = BH_SNE().computeGaussianPerplexity(X, perplexity)
    else:
        P = __x2p_approx(X, perplexity, method=approx_method, verbose=verbose)

    return P


def __x2p_approx(X, perplexity=50, method='vptree', verbose=False):
    k = 3 * perplexity
    N = X.shape[0]

    distances, indices = knn(X, k, method=method, verbose=verbose)

    if verbose:
        print('Finding beta and P...')

    P, beta = __find_betas(np.square(distances), perplexity, verbose=verbose)
    rows = np.repeat(range(P.shape[0]), P.shape[1])
    cols = indices.flatten()
    data = P.flatten()

    P = sp.sparse.csr_matrix((data, (rows, cols)), shape=(N, N))
    P += P.T
    P /= P.sum()

    return P


def __find_betas(D, perplexity=50, tol=1e-5, print_iter=1000, max_tries=50, verbose=False):
    def Hbeta(D, beta):
        P = np.exp(-D * beta)
        sumP = np.sum(P)
        H = np.log(sumP) + beta * np.sum((D * P)) / sumP
        P = P / sumP
        return H, P

    N = D.shape[0]
    k = D.shape[1]
    P = np.zeros((N, k), dtype=np.float32)
    beta = np.ones(N)
    logU = np.log(perplexity)

    if verbose:
        print('Computing P and betas...')

    for i in range(N):
        if verbose and print_iter and i % print_iter == 0:
            print('Computed P-values {} of {} datapoints...'.format(i, N))

        # Set minimum and maximum values for precision
        betamin = float('-inf')
        betamax = float('+inf')

        Di = D[i]
        H, thisP = Hbeta(Di, beta[i])

        Hdiff = H - logU
        tries = 0
        while abs(Hdiff) > tol and tries < max_tries:
            if Hdiff > 0:
                betamin = beta[i]
                if np.isinf(betamax):
                    beta[i] *= 2
                else:
                    beta[i] = (beta[i] + betamax) / 2
            else:
                betamax = beta[i]
                if np.isinf(betamin):
                    beta[i] /= 2
                else:
                    beta[i] = (beta[i] + betamin) / 2
            H, thisP = Hbeta(Di, beta[i])
            Hdiff = H - logU
            tries += 1
        P[i] = thisP[:]

    if verbose:
        print('Mean value of sigma: {}'.format(np.mean(np.sqrt(1 / beta))))
        print('Minimum value of sigma: {}'.format(np.min(np.sqrt(1 / beta))))
        print('Maximum value of sigma: {}'.format(np.max(np.sqrt(1 / beta))))

    return P, beta
