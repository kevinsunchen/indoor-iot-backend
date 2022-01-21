import itertools
import numpy as np
import scipy.optimize
# from . import localize # TODO fix chained imports for globals

##
# This is an iterative approach for localization.
# Algorithm:
#   Main idea: Let's say S(n, k) is set of all valid intersections until n-th
#   measurements using exactly k measurements.
#   Then S(n, k) can be recursively defined as
#       S(n,k) = S(n-1,k) + all valid intersection of n-th measurement with S(n-1,k-1)
#
#   Pruning:
#       S(n,k) can become quite large. There are couple pruning techniques to optimize.
#       1. Only keep valid intersections where residual cost is low. See pruneOnlyValidIntersections()
#       2. Don't need to iterate through all k where 0<=k<=n. We can start k at n
#          and keep decreasing until we find k where S(n, k) contains an intersection
#          with pretty small residual cost. See stopCondition()
#       3. Don't need to book-keep all S(N,*) for all N. Only need the previous (aka N-1).
#       4. Deduplicate intersections that are close to each other. See pruneDeduplicateCloseIntersections()
#
class MultiFusion:
    def __init__(self, bound_min, bound_max, early_return=True):
        self.num_of_rx = 0
        self.bound_min = bound_min
        self.bound_max = bound_max
        self.prev = {}
        self.prev[0] = self.getBaseCase()
        self.RESIDUAL_COST_THR = 0.05
        self.REALLY_GOOD_RESIDUAL_PERCENTAGE = 0.4
        self.ABSOLUTE_RESIDUAL_THRESHOLD = -7.0#-10#-7.0
        self.DISTANCE_THRESHOLD = 0.1#0.32#0.1
        self.PRUNE_CLOSE_DISTANCE_THRESHOLD = 0.01
        self.run_early_return = early_return

    def getBaseCase(self):
        return [
            {
                'cartesian_product': [],
                'combined_cluster_cost': np.nan,
                'location': np.nan,
                'residual_cost': np.nan,
                'rx_locs': [],
                'tx_locs': [],
                'tx_indices': [],
                'num_zero_cand': 0,
                'num_one_cand': 0,
                'num_two_cand': 0,
            },
        ]

    # Public facing function
    def process_new_measurement(
        self,
        clusters,
        rx_loc,
        tx_loc,
    ):
        """Compute localization algo based on a new measurement"""
        self.num_of_rx = self.num_of_rx + 1
        cur = {}

        k = self.num_of_rx

        while k >= 0:
            if k == 0:
                cur[0] = self.getBaseCase()
                break


            # The main recursive definition.
            cur[k] = self.prev[k].copy() if k in self.prev else []
            if k-1 in self.prev:
                cur[k] += self.intersect(
                    k,
                    clusters,
                    rx_loc,
                    tx_loc,
                    self.prev[k-1].copy(),
                )

            cur[k].sort(key=lambda p: p['residual_cost'])

            if self.stopCondition(k, cur[k]):
                break
            else:
                k -= 1

        self.prev = cur
        self.prune()

    def stopCondition(self, k, solutions):
        """
        Complete localization if least-square residual is below
        threshold.
        """

        if k <= 3:
            return False

        if not solutions:
            return False

        min_p_cost = solutions[0]['residual_cost']
        min_p_cost = np.log(min_p_cost)
        
        if (min_p_cost < self.ABSOLUTE_RESIDUAL_THRESHOLD):
            # print('Achieved very good cost !')
            pass
        return (min_p_cost < self.ABSOLUTE_RESIDUAL_THRESHOLD)

    def prune(self):
        """
        Remove unnecessary location intersections based on valid or
        too close to each other.
        """

        for k in self.prev.keys():
            before = len(self.prev[k])
            # self.pruneOnlyValidIntersections(k)
            # self.pruneDeduplicateCloseIntersections(k)
            # if len(self.prev[k]) > 0:
            #     print(
            #         "N ", self.num_of_rx,
            #         " k ", k,
            #         " minimum res cost", self.prev[k][0]['residual_cost'],
            #         "length before pruned", before,
            #         "length after pruned" , len(self.prev[k]),
            #     )

    def pruneOnlyValidIntersections(self, k):
        if (k <=2):
            return

        if not self.prev[k]:
            return

        min_p_cost = self.prev[k][0]['residual_cost']
        min_p_cost = np.log(min_p_cost)

        pruned = []

        # Remove solutions that are much greater than the minimum.
        for solution in self.prev[k]:
            cost = np.log(solution['residual_cost'])
            if cost < self.REALLY_GOOD_RESIDUAL_PERCENTAGE * min_p_cost:
                pruned.append(solution)

        self.prev[k] = pruned

    def pruneDeduplicateCloseIntersections(self, k):
        if (k <=2):
            return

        if not self.prev[k]:
            return

        pruned = []

        # Remove solutions that are close to existing solutions.
        for solution in self.prev[k]:
            close_found = False
            for other_solution in pruned:
                distance = np.linalg.norm(
                    np.array(other_solution['location']) - np.array(solution['location'])
                )
                if distance < self.PRUNE_CLOSE_DISTANCE_THRESHOLD: # Less than a centimeter
                    close_found = True
                    break

            if not close_found:
                pruned.append(solution)

        self.prev[k] = pruned

    def intersect(
        self,
        k,
        clusters,
        rx_loc,
        tx_loc,
        prev_solutions,
    ):
        solutions = []

        # Intersect with all previous solutions.
        for prev_solution in prev_solutions:
            prev_cartesian_product = prev_solution['cartesian_product']
            prev_rx_locs = prev_solution['rx_locs']
            rx_locs = prev_rx_locs.copy()
            rx_locs.append(rx_loc)
            prev_tx_locs = prev_solution['tx_locs']
            tx_locs = prev_tx_locs.copy()
            tx_locs.append(tx_loc)
            prev_tx_indices = prev_solution['tx_indices']
            tx_indices = prev_tx_indices.copy()
            tx_indices.append(self.num_of_rx)

            for cluster_ind, cluster in enumerate(clusters):
                num_zero_cand = prev_solution['num_zero_cand'] + (1 if cluster_ind == 0 else 0)
                num_one_cand = prev_solution['num_one_cand'] + (1 if cluster_ind == 1 else 0)
                num_two_cand = prev_solution['num_two_cand'] + (1 if cluster_ind == 2 else 0)

                if (not np.isfinite(cluster[0])):
                    continue

                cartesian_product = prev_cartesian_product.copy()
                cartesian_product.append(cluster)
                combined_cluster_cost = np.sum(cartesian_product, axis=0)[1]

                # Find the intersection.

                est_loc = self.findIntersection(
                    prev_solution['location'],
                    cluster[0],
                    np.array(cartesian_product)[:,0],
                    np.array(rx_locs),
                    np.array(tx_locs),
                )

                # If valid intersection
                if est_loc is not None:
                    # (loc, residual_cost) = est_loc
                    loc, residual_cost = est_loc[:-1], est_loc[-1]

                    solutions.append({
                        'cartesian_product': cartesian_product,
                        'combined_cluster_cost': combined_cluster_cost,
                        'location': loc,
                        'residual_cost': residual_cost,
                        'rx_locs': rx_locs,
                        'tx_locs': tx_locs,
                        'num_zero_cand': num_zero_cand,
                        'num_one_cand': num_one_cand,
                        'num_two_cand': num_two_cand,
                        'tx_indices': tx_indices,
                    })

        return solutions

    def findIntersection(
        self,
        prev_location,
        cluster_distance,
        final_dists,
        rx_locs,
        tx_locs,
    ):
        if len(final_dists) <= 2:
            return (np.nan, np.nan)

        # Step 1: Early return without running least_squares method.
        # Check if the point is much further away from previous intersection.
        prev_location = np.array(prev_location)
        rx_loc = np.array(rx_locs[-1])
        tx_loc = np.array(tx_locs[-1])
        new_oob_to_prev = np.linalg.norm(prev_location - rx_loc) + np.linalg.norm(prev_location - tx_loc)
        err = np.abs(new_oob_to_prev - cluster_distance)
        # if self.run_early_return and err > self.DISTANCE_THRESHOLD:
        if err > self.DISTANCE_THRESHOLD:
            # pass
            # print(f'Not running intersection for {len(tx_locs)}')
            return None

        # Step 2: Actually check intersection with least square
        guess = (self.bound_min + self.bound_max) / 2.0
        # tx_locs = np.tile(self.tx_loc, (rx_locs.shape[0], 1))
        cal_loc = guess
        est_loc = single_least_squares(
            final_dists,
            guess,
            tx_locs,
            rx_locs,
            cal_loc,
            rx_locs.shape[0],
            cost_thresh=self.RESIDUAL_COST_THR,
            bounds=(self.bound_min, self.bound_max),
        )
        # print("error ", err, "est_loc", est_loc)
        return est_loc


    def get_best_location_per_k(self, k, solutions):
        if not solutions:
            return None

        best = min(
            solutions,
            key=lambda p:
                p['residual_cost']
        )
        return {
            'location': best['location'],
            'residual_cost': best['residual_cost'],
            'combined_cluster_cost': best['combined_cluster_cost'],
            'k': k,
            'norm_residual_cost': best['residual_cost'] / k
        }

    # Public function.
    def get_best_location_candidates(self):
        best_candidates = []

        for k in self.prev.keys():
            if k < 3:
                continue
            candidate = self.get_best_location_per_k(
                k,
                self.prev[k],
            )

            if candidate is not None:
                best_candidates.append(candidate)

        return best_candidates

    def get_all_locations(self):
        best_candidates = []

        for k in self.prev.keys():
            if k < 3:
                continue
            for sol in self.prev[k]:
                best_candidates.append({'location': sol['location'],
                                        'tx_locs': sol['tx_locs'],
                                        'num_zero_cand': sol['num_zero_cand'],
                                        'num_one_cand': sol['num_one_cand'],
                                        'num_two_cand': sol['num_two_cand'],
                                        'combined_cluster_cost': sol['combined_cluster_cost'],
                                        'residual_cost': sol['residual_cost'],
                                        'tx_indices': sol['tx_indices']})

        return best_candidates



def single_least_squares(dists, guess, tx_locs, rx_locs, cal_loc, num_oob_rx, cost_thresh=np.inf, **ls_kwargs):
    """
        Takes the two integer wavelength distances from each OOB receiver
        and computes the most likely location

        dists:: n length ndarray : The distance from each OOB pair
        guess:: D length ndarray : Guessed distance to start each optimization

        Returns: D + 1 length ndarray:  dimensional location estimate, mean(abs(residuals))
    """
    def get_dists(p):
        return np.linalg.norm(p - tx_locs[:num_oob_rx, :], axis=1) + np.linalg.norm(p - rx_locs[:num_oob_rx, :], axis=1)

    def residual_maker(dists):
        # Returns residual function that corrects 2D estimates to work with 3D antennas location
        p_prime = cal_loc.copy()
        def residuals(p):
            p_prime[:p.shape[0]] = p
            return (get_dists(p_prime) - dists)
        return residuals

    p = scipy.optimize.least_squares(residual_maker(dists), guess, **ls_kwargs)
    # print(p)
    # Make sure answer not on any of the bounds (likely bad solution)
    if p.success and p.cost < cost_thresh and np.all(p.active_mask == 0):
        # print(f'Success: {p.x}')
        return np.hstack((p.x, p.cost))
    else:
        return None