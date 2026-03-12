from evac_sim.core.environment_info import EnvironmentInfo


def test_environment_info_creation():
    env = EnvironmentInfo(
        graph="graph",
        paths_connection="db",
    )

    assert env.graph == "graph"
    assert env.paths_connection == "db"
    assert env.floors is None
    assert env.floor_number == 1
    assert env.floor_connecting_nodes == {}
    assert env.floor_paths == {}


def test_environment_info_independent_dicts():
    env1 = EnvironmentInfo(graph="g1", paths_connection="db")
    env2 = EnvironmentInfo(graph="g2", paths_connection="db")

    env1.floor_paths["A"] = "path"

    assert env2.floor_paths == {}