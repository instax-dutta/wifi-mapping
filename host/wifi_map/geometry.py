"""SfW-lite geometry: turn RSSI into wall counts (k) via unsupervised thresholds.

Follows Fafoutis et al. (WF-IoT 2015) and the SfW paper (arXiv 2403.02235):
k-means over RSSI yields K+1 centroids; midpoints between consecutive centroids
are the thresholds that map a measurement to a wall count k.

Phase 3 (P2 Geometry): sparse inverse k-visibility (Structure from WiFi, Kim et
al. 2024, arXiv 2403.02235 / 2408.07757). Turns RSSI shadowing (k-values) into
a coarse free-space / occupancy grid plus a per-cell wall probability map.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np


def kmeans_1d(values: np.ndarray, k: int, iters: int = 100, seed: int = 0) -> np.ndarray:
    """Return k ascending 1D k-means centroids."""
    v = np.asarray(values, dtype=float).ravel()
    if v.size == 0:
        return np.array([], dtype=float)
    k = max(1, min(k, v.size))
    rng = np.random.default_rng(seed)
    centroids = np.sort(rng.choice(v, size=k, replace=False))
    for _ in range(iters):
        assign = np.argmin(np.abs(v[:, None] - centroids[None, :]), axis=1)
        new = centroids.copy()
        for i in range(k):
            members = v[assign == i]
            if members.size:
                new[i] = members.mean()
        if np.allclose(new, centroids):
            break
        centroids = new
    return np.sort(centroids)


def k_thresholds(rssis: Sequence[float], k_max: int = 3, seed: int = 0) -> List[float]:
    """Thresholds separating k=0..k_max. Descending RSSI means fewer walls."""
    v = np.asarray(rssis, dtype=float).ravel()
    if v.size < k_max + 1:
        return []
    centroids = kmeans_1d(v, k_max + 1, seed=seed)   # ascending
    desc = centroids[::-1]                            # strongest -> weakest
    return [float((desc[i] + desc[i + 1]) / 2.0) for i in range(len(desc) - 1)]


def assign_k(rssi: float, thresholds: Sequence[float]) -> int:
    """Number of walls crossed for a measurement, given descending thresholds."""
    k = 0
    for t in thresholds:
        if rssi <= t:
            k += 1
    return k


def fit_path_loss(distances: Sequence[float], rssis: Sequence[float]) -> Tuple[float, float]:
    """Fit rssi = P0 - 10 n log10(d). Returns (P0, n)."""
    d = np.asarray(distances, dtype=float).ravel()
    r = np.asarray(rssis, dtype=float).ravel()
    mask = np.isfinite(d) & np.isfinite(r) & (d > 0)
    d, r = d[mask], r[mask]
    if d.size < 2:
        return float("nan"), float("nan")
    slope, intercept = np.polyfit(np.log10(d), r, 1)
    return float(intercept), float(-slope / 10.0)


# ---------------------------------------------------------------------------
# Phase 3: sparse inverse k-visibility (Structure from WiFi)
# ---------------------------------------------------------------------------


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> List[Tuple[int, int]]:
    """Integer grid cells along the line from (x0, y0) to (x1, y1), inclusive.

    Pure Bresenham rasterization. Returns a list of (x, y) cell tuples.
    """
    x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
    cells: List[Tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    while True:
        cells.append((x0, y0))
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x0 += sx
        if e2 < dx:
            err += dx
            y0 += sy
    return cells


def world_to_grid(pos: Sequence[float], origin: Sequence[float],
                  resolution: float) -> Tuple[int, int]:
    """Convert a world position to grid cell indices (gx, gy)."""
    x, y = float(pos[0]), float(pos[1])
    ox, oy = float(origin[0]), float(origin[1])
    res = float(resolution)
    return int(np.floor((x - ox) / res)), int(np.floor((y - oy) / res))


def grid_to_world(cell: Sequence[int], origin: Sequence[float],
                  resolution: float) -> Tuple[float, float]:
    """Convert grid cell indices to the world coordinate of the cell center."""
    gx, gy = int(cell[0]), int(cell[1])
    ox, oy = float(origin[0]), float(origin[1])
    res = float(resolution)
    return (ox + (gx + 0.5) * res, oy + (gy + 0.5) * res)


def ray_cells(start_world: Sequence[float], end_world: Sequence[float],
              origin: Sequence[float], resolution: float) -> List[Tuple[int, int]]:
    """Rasterize a world-space line segment into grid cells (Bresenham)."""
    c0 = world_to_grid(start_world, origin, resolution)
    c1 = world_to_grid(end_world, origin, resolution)
    return bresenham_line(c0[0], c0[1], c1[0], c1[1])


def sparse_inverse_k_visibility(
    points: np.ndarray,
    k_values: np.ndarray,
    router_pos: Sequence[float],
    bounds: Sequence[float],
    resolution: float,
    gaussian_sigma_m: float | None = None,
    occupied_threshold: float = 0.5,
    angle_tol: float = 1e-4,
) -> Tuple[np.ndarray, np.ndarray, Dict]:
    """Sparse inverse k-visibility: coarse occupancy grid from k-values.

    Parameters
    ----------
    points : (N, 2) array
        Trajectory points in world coords.
    k_values : (N,) array of int
        Wall count k per trajectory point.
    router_pos : (rx, ry)
        World coords of the reference transmitter.
    bounds : (xmin, xmax, ymin, ymax)
        Grid bounds in world coords.
    resolution : float
        Metres per grid cell.
    gaussian_sigma_m : float, optional
        Gaussian width (metres) for wall probability modes. Defaults to
        ``resolution``.
    occupied_threshold : float
        Wall probability at/above which a cell is marked occupied.
    angle_tol : float
        Max angle difference (rad) for points to be considered on the same ray
        from the router.

    Returns
    -------
    occupancy_grid : (ny, nx) int8
        -1 = unknown, 0 = occupied, 1 = free.
    wall_probability : (ny, nx) float32
        0-1 probability of a wall at each cell.
    metadata : dict
        grid shape, origin, resolution, bounds, n_free, n_occupied, n_unknown.
    """
    points = np.asarray(points, dtype=float).reshape(-1, 2)
    k_values = np.asarray(k_values, dtype=int).ravel()
    router_pos = np.asarray(router_pos, dtype=float).ravel()
    xmin, xmax, ymin, ymax = (float(v) for v in bounds)
    res = float(resolution)
    if res <= 0:
        raise ValueError("resolution must be positive")
    n = int(points.shape[0])
    if k_values.shape[0] != n:
        raise ValueError("points and k_values must have the same length")

    nx = max(1, int(np.ceil((xmax - xmin) / res)))
    ny = max(1, int(np.ceil((ymax - ymin) / res)))
    origin = (xmin, ymin)

    occupancy = np.full((ny, nx), -1, dtype=np.int8)
    wall_prob = np.zeros((ny, nx), dtype=np.float32)

    def in_grid(gx: int, gy: int) -> bool:
        return 0 <= gx < nx and 0 <= gy < ny

    def mark_free(cells: Sequence[Tuple[int, int]]) -> None:
        for gx, gy in cells:
            if in_grid(gx, gy):
                occupancy[gy, gx] = 1

    sigma = gaussian_sigma_m if gaussian_sigma_m is not None else res
    sigma_cell = sigma / res
    radius_cell = max(1, int(np.ceil(3.0 * sigma_cell)))

    def add_gaussian(center_world: np.ndarray, weight: float = 1.0) -> None:
        cx, cy = world_to_grid(center_world, origin, res)
        x0 = max(0, cx - radius_cell)
        x1 = min(nx, cx + radius_cell + 1)
        y0 = max(0, cy - radius_cell)
        y1 = min(ny, cy + radius_cell + 1)
        cwx, cwy = float(center_world[0]), float(center_world[1])
        for gy in range(y0, y1):
            for gx in range(x0, x1):
                wx, wy = grid_to_world((gx, gy), origin, res)
                d = float(np.hypot(wx - cwx, wy - cwy))
                p = float(weight) * float(np.exp(-0.5 * (d / sigma) ** 2))
                if p <= 0:
                    continue
                old = float(wall_prob[gy, gx])
                wall_prob[gy, gx] = np.float32(1.0 - (1.0 - old) * (1.0 - p))

    r_cell = world_to_grid(router_pos, origin, res)

    # Grid cell of each trajectory point.
    p_cells = np.array([world_to_grid(p, origin, res) for p in points], dtype=int)

    # Rule 1: trajectory points are free space.
    mark_free(p_cells.tolist())

    # Rule 2: k == 0 at point p => entire ray R -> p is free space.
    for i in range(n):
        if int(k_values[i]) == 0:
            mark_free(ray_cells(router_pos, points[i], origin, res))

    # Group trajectory points by ray from the router, sorted by distance.
    # Points on the same ray share an angle from the router (mod 2*pi).
    groups: List[List[int]] = []
    if n > 0:
        dvec = points - router_pos[None, :]
        angles = np.arctan2(dvec[:, 1], dvec[:, 0])
        dists = np.hypot(dvec[:, 0], dvec[:, 1])
        order = np.argsort(angles)
        sa = angles[order]
        gaps = np.diff(sa)
        wrap_gap = sa[0] + 2.0 * np.pi - sa[-1]
        all_gaps = np.append(gaps, wrap_gap)
        cut = int(np.argmax(all_gaps))
        if cut == n - 1:
            ro = order
        else:
            ro = np.concatenate([order[cut + 1:], order[:cut + 1]])
        cur = [int(ro[0])]
        for idx in ro[1:]:
            idx = int(idx)
            if abs(float(angles[idx]) - float(angles[cur[-1]])) <= angle_tol:
                cur.append(idx)
            else:
                groups.append(cur)
                cur = [idx]
        groups.append(cur)

    # Rules 3 & 4 and Part 2: walk each ray from the router outward.
    for group in groups:
        group_sorted = sorted(group, key=lambda i: float(dists[i]))
        # Virtual router point at distance 0 with k == 0, so the first segment
        # (R -> closest point) is accounted for (Rule 3).
        seq_pos = [router_pos]
        seq_k = [0]
        seq_d = [0.0]
        for i in group_sorted:
            seq_pos.append(points[i])
            seq_k.append(int(k_values[i]))
            seq_d.append(float(dists[i]))
        for a in range(len(seq_pos) - 1):
            pa = seq_pos[a]
            pb = seq_pos[a + 1]
            dk = seq_k[a + 1] - seq_k[a]
            cells = ray_cells(pa, pb, origin, res)
            if dk == 0:
                # Rule 4 / Part 2: same k on a ray => free space between them.
                mark_free(cells)
            elif dk == 1:
                # Part 2: exactly one wall; unimodal Gaussian at midpoint.
                mid = (pa + pb) / 2.0
                add_gaussian(np.asarray(mid, dtype=float), 1.0)
            elif dk > 1:
                # Part 2: multiple walls; multimodal distribution along segment.
                for m in range(1, int(dk) + 1):
                    t = m / (int(dk) + 1.0)
                    c = pa + t * (pb - pa)
                    add_gaussian(np.asarray(c, dtype=float), 1.0 / int(dk))
            # dk < 0: wall count decreased along the ray (physically
            # inconsistent / noise); leave cells untouched.

    # Free space takes precedence over any wall probability.
    wall_prob[occupancy == 1] = 0.0

    # Occupied: wall probability above threshold on cells not already free.
    occ_mask = (wall_prob >= float(occupied_threshold)) & (occupancy != 1)
    occupancy[occ_mask] = 0

    n_free = int(np.count_nonzero(occupancy == 1))
    n_occupied = int(np.count_nonzero(occupancy == 0))
    n_unknown = int(np.count_nonzero(occupancy == -1))

    metadata: Dict = {
        "grid_shape": [int(ny), int(nx)],
        "origin": [float(xmin), float(ymin)],
        "resolution": float(res),
        "bounds": [float(xmin), float(xmax), float(ymin), float(ymax)],
        "router_pos": [float(router_pos[0]), float(router_pos[1])],
        "n_points": int(n),
        "n_free": n_free,
        "n_occupied": n_occupied,
        "n_unknown": n_unknown,
        "occupied_threshold": float(occupied_threshold),
        "gaussian_sigma_m": float(sigma),
    }
    return occupancy, wall_prob, metadata
