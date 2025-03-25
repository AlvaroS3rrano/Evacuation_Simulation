import shapely
import pedpy
class Floor:
    """
    Represents a building floor.

    Attributes:
        name: Name of the floor.
        complete_area: Total area of the floor (Polygon).
        obstacles: List of obstacles (Polygons).
        exit_polygons: Dictionary of exit polygons.
        waypoints: Dictionary of waypoints.
        distribution_polygons: Dictionary of distribution areas.
        sources: Starting node(s).
        targets: Target node(s).
        specific_areas: Dictionary of specific areas.
        obstacle: The union of all obstacles.
        walkable_area: Walkable area computed as the difference between complete_area and obstacles.
    """

    def __init__(self, name, graph, complete_area, obstacles, exit_polygons, waypoints,
                 distribution_polygons, sources, targets, specific_areas):
        self.name = name
        self.graph = graph
        self.complete_area = complete_area
        self.obstacles = obstacles
        self.exit_polygons = exit_polygons
        self.waypoints = waypoints
        self.distribution_polygons = distribution_polygons
        self.sources = sources
        self.targets = targets
        self.specific_areas = specific_areas

        # Derived attributes
        self.obstacle = shapely.union_all(self.obstacles)
        self.walkable_area = pedpy.WalkableArea(
            shapely.difference(self.complete_area, self.obstacle)
        )