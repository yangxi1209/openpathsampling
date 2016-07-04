from test_helpers import (raises_with_message_like, data_filename,
                          CalvinistDynamics, make_1d_traj)
from nose.tools import (assert_equal, assert_not_equal, assert_items_equal,
                        raises, assert_almost_equal, assert_true)
from nose.plugins.skip import SkipTest

from openpathsampling.pathsimulator import *
import openpathsampling as paths
import openpathsampling.engines.toy as toys
import numpy as np
import os

import logging
logging.getLogger('openpathsampling.initialization').setLevel(logging.CRITICAL)
logging.getLogger('openpathsampling.storage').setLevel(logging.CRITICAL)
logging.getLogger('openpathsampling.netcdfplus').setLevel(logging.CRITICAL)
logging.getLogger('openpathsampling.ensemble').setLevel(logging.CRITICAL)
logging.getLogger('openpathsampling.engines').setLevel(logging.CRITICAL)

class testAbstract(object):
    @raises_with_message_like(TypeError, "Can't instantiate abstract class")
    def test_abstract_volume(self):
        mover = PathSimulator()


class testFullBootstrapping(object):
    def setup(self):
        self.cv = paths.CV_Function("Id", lambda snap: snap.xyz[0][0])
        cv_neg = paths.CV_Function("Neg", lambda snap: -snap.xyz[0][0])
        self.stateA = paths.CVRangeVolume(self.cv, -1.0, 0.0)
        self.stateB = paths.CVRangeVolume(self.cv, 1.0, 2.0)
        self.stateC = paths.CVRangeVolume(self.cv, 3.0, 4.0)
        interfacesAB = paths.VolumeFactory.CVRangeVolumeSet(
            self.cv, -1.0, [0.0, 0.2, 0.4]
        )
        interfacesBC = paths.VolumeFactory.CVRangeVolumeSet(
            self.cv, 1.0, [2.0, 2.2, 2.4]
        )
        interfacesBA = paths.VolumeFactory.CVRangeVolumeSet(
            cv_neg, -1.0, [-1.0, -0.8, -0.6]
        )

        network = paths.MISTISNetwork([
            (self.stateA, interfacesAB, self.cv, self.stateB),
            (self.stateB, interfacesBC, self.cv, self.stateC),
            (self.stateB, interfacesBA, cv_neg, self.stateA)
        ])
        self.tisAB = network.input_transitions[(self.stateA, self.stateB)]
        self.tisBC = network.input_transitions[(self.stateB, self.stateC)]
        self.tisBA = network.input_transitions[(self.stateB, self.stateA)]
        self.network = network
        self.snapA = make_1d_traj([-0.5])[0]

        self.noforbid_noextra_AB = paths.FullBootstrapping(
            transition=self.tisAB,
            snapshot=self.snapA
        )

    @raises(RuntimeError)
    def test_initial_max_length(self):
        engine = CalvinistDynamics([-0.5, -0.4, -0.3, -0.2, -0.1, 0.1, -0.1])
        bootstrap_AB_maxlength = paths.FullBootstrapping(
            transition=self.tisAB,
            snapshot=self.snapA,
            initial_max_length = 3,
            engine=engine
        )
        bootstrap_AB_maxlength.output_stream = open(os.devnull, "w")
        gs = bootstrap_AB_maxlength.run(build_attempts=1)

    def test_first_traj_ensemble(self):
        traj_starts_in = make_1d_traj([-0.2, -0.1, 0.1, -0.1])
        traj_starts_out = make_1d_traj([0.1, -0.1, 0.1, -0.1])
        traj_not_good = make_1d_traj([0.1, -0.1, 0.1])
        first_traj_ens = self.noforbid_noextra_AB.first_traj_ensemble
        assert_equal(first_traj_ens(traj_starts_in), True)
        assert_equal(first_traj_ens(traj_starts_out), True)
        assert_equal(first_traj_ens(traj_not_good), False)

    def test_sampling_ensembles(self):
        traj1 = make_1d_traj([-0.2, -0.1, 0.1, -0.1])
        traj2 = make_1d_traj([-0.1, 0.1, -0.1])
        traj3 = make_1d_traj([-0.1, 0.1, 0.3, -0.1])
        traj4 = make_1d_traj([0.1, 0.3, 0.1])
        all_ensembles = self.noforbid_noextra_AB.all_ensembles
        assert_equal(len(all_ensembles), 3)
        for ens in all_ensembles:
            assert_equal(ens(traj1), False)
            assert_equal(ens(traj4), False)
        assert_equal(all_ensembles[0](traj2), True)
        assert_equal(all_ensembles[0](traj3), True)
        assert_equal(all_ensembles[1](traj2), False)
        assert_equal(all_ensembles[1](traj3), True)
        assert_equal(all_ensembles[2](traj2), False)
        assert_equal(all_ensembles[2](traj3), False)

    def test_run_already_satisfied(self):
        engine = CalvinistDynamics([-0.5, 0.8, -0.1])
        bootstrap = FullBootstrapping(
            transition=self.tisAB,
            snapshot=self.snapA,
            engine=engine
        )
        bootstrap.output_stream = open(os.devnull, "w")
        gs = bootstrap.run()
        assert_equal(len(gs), 3)

    def test_run_extra_interfaces(self):
        engine = CalvinistDynamics([-0.5, 0.8, -0.1])
        bootstrap = FullBootstrapping(
            transition=self.tisAB,
            snapshot=self.snapA,
            engine=engine,
            extra_interfaces=[paths.CVRangeVolume(self.cv, -1.0, 0.6)]
        )
        bootstrap.output_stream = open(os.devnull, "w")
        gs = bootstrap.run()
        assert_equal(len(gs), 4)

    def test_run_forbidden_states(self):
        engine = CalvinistDynamics([-0.5, 0.3, 3.2, -0.1, 0.8, -0.1])
        # first, without setting forbidden_states
        bootstrap1 = FullBootstrapping(
            transition=self.tisAB,
            snapshot=self.snapA,
            engine=engine
        )
        bootstrap1.output_stream = open(os.devnull, "w")
        gs1 = bootstrap1.run()
        assert_equal(len(gs1), 3)
        assert_items_equal(self.cv(gs1[0]), [-0.5, 0.3, 3.2, -0.1])
        # now with setting forbidden_states
        bootstrap2 = FullBootstrapping(
            transition=self.tisAB,
            snapshot=self.snapA,
            engine=engine,
            forbidden_states=[self.stateC]
        )
        bootstrap2.output_stream = open(os.devnull, "w")
        # make sure this is where we get the error
        try:
            gs2 = bootstrap2.run()
        except RuntimeError:
            pass

    @raises(RuntimeError)
    def test_too_much_bootstrapping(self):
        engine = CalvinistDynamics([-0.5, 0.2, -0.1])
        bootstrap = FullBootstrapping(
            transition=self.tisAB,
            snapshot=self.snapA,
            engine=engine,
        )
        bootstrap.output_stream = open(os.devnull, "w")
        gs = bootstrap.run(max_ensemble_rounds=1)

class testCommittorSimulation(object):
    def setup(self):
        # As a test system, let's use 1D motion on a flat potential. If the
        # velocity is positive, you right the state on the right. If it is
        # negative, you hit the state on the left.
        pes = toys.LinearSlope(m=[0.0], c=[0.0]) # flat line
        topology = toys.Topology(n_spatial=1, masses=[1.0], pes=pes)
        integrator = toys.LeapfrogVerletIntegrator(0.1)
        options = {
            'integ': integrator,
            'n_frames_max': 100000,
            'nsteps_per_frame': 5
        }
        self.engine = toys.Engine(options=options, topology=topology)
        self.snap0 = toys.Snapshot(coordinates=np.array([[0.0]]),
                                   velocities=np.array([[1.0]]),
                                   engine=self.engine)
        cv = paths.CV_Function("Id", lambda snap : snap.coordinates[0][0])
        self.left = paths.CVRangeVolume(cv, float("-inf"), -1.0)
        self.right = paths.CVRangeVolume(cv, 1.0, float("inf"))
        self.state_labels = {"Left" : self.left,
                             "Right" : self.right,
                             "None" : ~(self.left | self.right)}

        randomizer = paths.NoModification()

        self.filename = data_filename("committor_test.nc")
        self.storage = paths.Storage(self.filename, 
                                     mode="w")
        self.storage.save(self.snap0)

        self.simulation = CommittorSimulation(storage=self.storage,
                                              engine=self.engine,
                                              states=[self.left, self.right],
                                              randomizer=randomizer,
                                              initial_snapshots=self.snap0)

    def teardown(self):
        if os.path.isfile(self.filename):
            os.remove(self.filename)
        paths.EngineMover.default_engine = None

    def test_initialization(self):
        sim = self.simulation  # convenience
        assert_equal(len(sim.initial_snapshots), 1)
        assert_true(isinstance(sim.mover, paths.RandomChoiceMover))

    def test_committor_run(self):
        self.simulation.run(n_per_snapshot=20)
        assert_equal(len(self.simulation.storage.steps), 20)
        counts = {'fwd' : 0, 'bkwd' : 0}
        for step in self.simulation.storage.steps:
            step.active.sanity_check()  # traj is in ensemble
            traj = step.active[0].trajectory
            traj_str = traj.summarize_by_volumes_str(self.state_labels)
            if traj_str == "None-Right":
                assert_equal(step.change.canonical.mover,
                             self.simulation.forward_mover)
                assert_equal(step.active[0].ensemble,
                             self.simulation.forward_ensemble)
                counts['fwd'] += 1
            elif traj_str == "Left-None":
                assert_equal(step.change.canonical.mover,
                             self.simulation.backward_mover)
                assert_equal(step.active[0].ensemble,
                             self.simulation.backward_ensemble)
                counts['bkwd'] += 1
            else:
                raise AssertionError(
                    str(traj_str) + "is neither 'None-Right' nor 'Left-None'"
                )
        assert_true(counts['fwd'] > 0)
        assert_true(counts['bkwd'] > 0)
        assert_equal(counts['fwd'] + counts['bkwd'], 20)

    def test_forward_only_committor(self):
        sim = CommittorSimulation(storage=self.storage,
                                  engine=self.engine,
                                  states=[self.left, self.right],
                                  randomizer=paths.NoModification(),
                                  initial_snapshots=self.snap0,
                                  direction=1)
        sim.run(n_per_snapshot=10)
        assert_equal(len(sim.storage.steps), 10)
        for step in self.simulation.storage.steps:
            s = step.active[0]
            step.active.sanity_check()  # traj is in ensemble
            assert_equal(
                s.trajectory.summarize_by_volumes_str(self.state_labels),
                "None-Right"
            )
            assert_equal(s.ensemble, sim.forward_ensemble)
            assert_equal(step.change.canonical.mover,
                         sim.forward_mover)

    def test_backward_only_committor(self):
        sim = CommittorSimulation(storage=self.storage,
                                  engine=self.engine,
                                  states=[self.left, self.right],
                                  randomizer=paths.NoModification(),
                                  initial_snapshots=self.snap0,
                                  direction=-1)
        sim.run(n_per_snapshot=10)
        assert_equal(len(sim.storage.steps), 10)
        for step in self.simulation.storage.steps:
            s = step.active[0]
            step.active.sanity_check()  # traj is in ensemble
            assert_equal(
                s.trajectory.summarize_by_volumes_str(self.state_labels),
                "Left-None"
            )
            assert_equal(s.ensemble, sim.backward_ensemble)
            assert_equal(step.change.canonical.mover,
                         sim.backward_mover)

    def test_multiple_initial_snapshots(self):
        snap1 = toys.Snapshot(coordinates=np.array([[0.1]]),
                              velocities=np.array([[-1.0]]),
                              engine=self.engine)
        sim = CommittorSimulation(storage=self.storage,
                                  engine=self.engine,
                                  states=[self.left, self.right],
                                  randomizer=paths.NoModification(),
                                  initial_snapshots=[self.snap0, snap1])
        sim.run(10)
        assert_equal(len(self.storage.steps), 20)
        snap0_coords = self.snap0.coordinates.tolist()
        snap1_coords = snap1.coordinates.tolist()
        count = {self.snap0: 0, snap1: 0}
        for step in self.storage.steps:
            # TODO: this should in step.change.canonical.details
            shooting_snap = step.change.trials[0].details.shooting_snapshot
            if shooting_snap.coordinates.tolist() == snap0_coords:
                mysnap = self.snap0
            elif shooting_snap.coordinates.tolist() == snap1_coords:
                mysnap = snap1
            else:
                msg = "Shooting snapshot matches neither test snapshot"
                raise AssertionError(msg)
            count[mysnap] += 1
        assert_equal(count, {self.snap0: 10, snap1: 10})

    def test_randomized_committor(self):
        raise SkipTest
        # this shows that we get both states even with forward-only
        # shooting, if the randomizer gives the negative velocities
        randomizer = paths.RandomVelocities(beta=1.0)
        sim = CommittorSimulation(storage=self.storage,
                                  engine=self.engine,
                                  states=[self.left, self.right],
                                  randomizer=randomizer,
                                  initial_snapshots=self.snap0,
                                  direction=1)
        sim.run(50)
        assert_equal(len(sim.storage.steps), 50)
        counts = {'None-Right' : 0,
                  'Left-None' : 0,
                  'None-Left' : 0,
                  'Right-None' : 0}
        for step in sim.storage.steps:
            step.active.sanity_check()  # traj is in ensemble
            traj = step.active[0].trajectory
            traj_str = traj.summarize_by_volumes_str(self.state_labels)
            try:
                counts[traj_str] += 1
            except KeyError:
                msg = "Got trajectory described as '{0}', length {1}"
                # this might be okay if it is 'None', length 100000
                raise AssertionError(msg.format(traj_str, len(traj)))
        assert_equal(counts['Left-None'], 0)
        assert_equal(counts['Right-None'], 0)
        assert_true(counts['None-Left'] > 0)
        assert_true(counts['None-Right'] > 0)
        assert_equal(sum(counts.values()), 50)

class testDirectSimulation(object):
    def setup(self):
        pes = toys.HarmonicOscillator(A=[1.0], omega=[1.0], x0=[0.0])
        topology = toys.Topology(n_spatial=1, masses=[1.0], pes=pes)
        integrator = toys.LeapfrogVerletIntegrator(0.1)
        options = {
            'integ': integrator,
            'n_frames_max': 100000,
            'nsteps_per_frame': 2
        }
        self.engine = toys.Engine(options=options, topology=topology)
        self.snap0 = toys.Snapshot(coordinates=np.array([[0.0]]),
                                   velocities=np.array([[1.0]]),
                                   engine=self.engine)
        cv = paths.CV_Function("Id", lambda snap : snap.coordinates[0][0])
        self.cv = cv
        self.center = paths.CVRangeVolume(cv, -0.2, 0.2)
        self.interface = paths.CVRangeVolume(cv, -0.3, 0.3)
        self.outside = paths.CVRangeVolume(cv, 0.6, 0.9)
        self.extra = paths.CVRangeVolume(cv, -1.5, -0.9)
        self.flux_pairs = [(self.center, self.interface)]
        self.sim = DirectSimulation(storage=None,
                                    engine=self.engine,
                                    states=[self.center, self.outside],
                                    flux_pairs=self.flux_pairs,
                                    initial_snapshot=self.snap0)

    def test_run(self):
        self.sim.run(200)
        assert_true(len(self.sim.transition_count) > 1)
        assert_true(len(self.sim.flux_events[self.flux_pairs[0]]) > 1)

    def test_transitions(self):
        # set fake data
        self.sim.transition_count = [
            (self.center, 1), (self.outside, 4), (self.center, 7),
            (self.extra, 10), (self.center, 12), (self.outside, 14)
        ]
        assert_equal(self.sim.n_transitions,
                     {(self.center, self.outside): 2,
                      (self.outside, self.center): 1,
                      (self.center, self.extra): 1,
                      (self.extra, self.center): 1})
        assert_equal(self.sim.transitions,
                     {(self.center, self.outside) : [3, 2],
                      (self.outside, self.center) : [3],
                      (self.center, self.extra): [3],
                      (self.extra, self.center): [2]})

    def test_rate_matrix(self):
        self.sim.states += [self.extra]
        self.sim.transition_count = [
            (self.center, 1), (self.outside, 4), (self.center, 7),
            (self.extra, 10), (self.center, 12), (self.outside, 14)
        ]
        # As of pandas 0.18.1, callables can be used in `df.loc`, etc. Since
        # we're using (callable) volumes for labels of columns/indices in
        # our dataframes, this sucks for us. Raise an issue with pandas?
        rate_matrix = self.sim.rate_matrix.as_matrix()
        nan = float("nan")
        test_matrix = np.array([[nan, 1.0/2.5, 1.0/3.0],
                                [1.0/3.0, nan, nan],
                                [1.0/2.0, nan, nan]])
        # for some reason, np.testing.assert_allclose(..., equal_nan=True)
        # was raising errors on this input. this hack gets the behavior
        for i in range(len(self.sim.states)):
            for j in range(len(self.sim.states)):
                if np.isnan(test_matrix[i][j]):
                    assert_true(np.isnan(rate_matrix[i][j]))
                else:
                    assert_almost_equal(rate_matrix[i][j],
                                        test_matrix[i][j])

    def test_fluxes(self):
        left_interface = paths.CVRangeVolume(self.cv, -0.3, float("inf"))
        right_interface = paths.CVRangeVolume(self.cv, float("-inf"), 0.3)
        sim = DirectSimulation(storage=None,
                               engine=self.engine,
                               states=[self.center, self.outside],
                               flux_pairs=[(self.center, left_interface),
                                           (self.center, right_interface)],
                               initial_snapshot=self.snap0)
        fake_flux_events = {(self.center, right_interface):
                            [(15, 3), (23, 15), (48, 23)],
                            (self.center, left_interface):
                            [(97, 34), (160, 97)]}
        sim.flux_events = fake_flux_events
        n_flux_events = {(self.center, right_interface): 3,
                         (self.center, left_interface): 2}
        assert_equal(sim.n_flux_events, n_flux_events)
        expected_fluxes = {(self.center, right_interface):
                           1.0 / (((15-3) + (23-15) + (48-23))/3.0),
                           (self.center, left_interface):
                           1.0 / (((97-34) + (160-97))/2.0)}
        for p in expected_fluxes:
            assert_almost_equal(sim.fluxes[p], expected_fluxes[p])

    def test_flux_from_calvinist_dynamics(self):
        # To check for the multiple interface set case, we need to have two 
        # dimensions. We can hack two "independent" dimensions from a one
        # dimensional system by making the second CV non-monotonic with the
        # first. For the full trajectory, we need snapshots `S` (in the
        # state); `I` (interstitial: outside the state, but not outside
        # either interface); `X_a` (outside interface alpha, not outside
        # interface beta); `X_b` (outside interface beta, not outside
        # interface alpha); and `X_ab` (outside interface alpha and beta).
        cv1 = self.cv
        cv2 = paths.CV_Function("abs_sin", 
                                lambda snap : np.abs(np.sin(snap.xyz[0][0])))
        state = paths.CVRangeVolume(cv1, -np.pi/8.0, np.pi/8.0)
        other_state = paths.CVRangeVolume(cv1, -5.0/8.0*np.pi, -3.0/8.0*np.pi)
        alpha = paths.CVRangeVolume(cv1, float("-inf"), 3.0/8.0*np.pi)
        beta = paths.CVRangeVolume(cv2, float("-inf"), np.sqrt(2)/2.0)
        # approx     alpha: x < 1.17   beta: abs(sin(x)) < 0.70
        S = 0              # cv1 =  0.00; cv2 = 0.00
        I = np.pi/5.0      # cv1 =  0.63; cv2 = 0.59
        X_a = np.pi        # cv1 =  3.14; cv2 = 0.00
        X_b = -np.pi/3.0   # cv1 = -1.05; cv2 = 0.87
        X_ab = np.pi/2.0   # cv1 =  1.57; cv2 = 1.00
        other = -np.pi/2.0 # cv1 = -1.57; cv2 = 1.00
        # That hack is utterly crazy, but I'm kinda proud of it!
        predetermined = [S, S, I, X_a,   # (2) first exit 
                         S, X_a,         # (4) cross A
                         S, X_ab,        # (6) cross A & B
                         I, S, X_b,      # (9) cross B
                         S, I, X_b,      # (12) cross B
                         other, I, X_b,  # (15) cross to other state
                         S, X_b,         # (17) first cross B
                         S, X_a,         # (19) first cross A
                         S, S, X_ab,     # (22) cross A & B
                         I, X_ab,        # (24) recrossing test
                         S, I,           # (26) false crossing test
                         S, S]
        engine = CalvinistDynamics(predetermined)
        init = make_1d_traj([S])
        sim = DirectSimulation(storage=None,
                               engine=engine,
                               states=[state, other_state],
                               flux_pairs=[(state, alpha), (state, beta)],
                               initial_snapshot=init[0])
        sim.run(len(predetermined)-1)
        # subtract 1 from the indices in `predetermined`, b/c 0 index of the
        # traj comes after the found initial step
        expected_flux_events = {
            (state, alpha): [(4, 2), (6, 4), (22, 19)],
            (state, beta): [(9, 6), (12, 9), (22, 17)]
        }
        assert_equal(len(sim.flux_events), 2)
        assert_equal(sim.flux_events[(state, alpha)],
                     expected_flux_events[(state, alpha)])
        assert_equal(sim.flux_events[(state, beta)],
                     expected_flux_events[(state, beta)])

    def test_sim_with_storage(self):
        tmpfile = data_filename("direct_sim_test.nc")
        if os.path.isfile(tmpfile):
            os.remove(tmpfile)

        storage = paths.Storage(tmpfile, "w", self.snap0)
        sim = DirectSimulation(storage=storage,
                               engine=self.engine,
                               states=[self.center, self.outside],
                               initial_snapshot=self.snap0)

        sim.run(200)
        storage.close()
        read_store = paths.AnalysisStorage(tmpfile)
        assert_equal(len(read_store.trajectories), 1)
        traj = read_store.trajectories[0]
        assert_equal(len(traj), 201)
        read_store.close()
        os.remove(tmpfile)
