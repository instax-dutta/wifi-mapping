# Prior art: WiFi radio mapping

Surveyed 2026-10-09. Goal: find what already exists so we build on it instead of
reinventing, and to pin down what a single ESP8266 can and cannot do.

## The landscape in one paragraph

Decades of work exist on turning WiFi radio measurements into position and shape.
The signal strength available on an ESP8266 is RSSI. RSSI is noisy (single-spot
jitter of ~35 dBm scan-to-scan is documented) and its relation to distance is
loose, so the field splits into: (a) **fingerprinting** - match a live RSSI
vector to a database of labelled fingerprints (robust but needs a survey), (b)
**model-based ranging** - convert RSSI to distance with a path-loss model and
triangulate (generalises but noisy), and (c) **geometry from shadowing** - infer
walls from how RSSI drops in discrete steps as signal crosses obstacles. The
most recent paper, Structure from WiFi, is the first to produce an explicit
occupancy map from RSSI alone, which is exactly the "map the surroundings" goal.

## Canonical papers

| Work | Year | Idea | Takeaway for us |
| --- | --- | --- | --- |
| Ferris, Fox, Lawrence, *WiFi-SLAM Using Gaussian Process Latent Variable Models* (IJCAI) | 2007 | Unlabeled high-dim RSSI vectors -> 2D latent space via GP-LVM; reconstructs a topological map and a sensor model for localization. | The reference point for WiFi-only SLAM. Needs a rich, high-dimensional RSSI vector (many APs) and a motion model. |
| Huang et al., *Efficient, Generalized Indoor WiFi GraphSLAM* (ICRA) | 2011 | GraphSLAM over RSSI to jointly estimate trajectory and AP positions. | Graph optimisation is the scalable route once we have odometry. |
| Fafoutis et al., *An RSSI-based wall prediction model for residential floor map construction* (WF-IoT) | 2015 | Maps RSSI -> number of walls **k** between sensor and AP using thresholds learned by k-means on RSSI. | The single most reusable primitive for us: k-means over RSSI gives wall-count thresholds with no labels. |
| Miyagusuku et al., *Improving GP mapping of wireless signals using path-loss models* (IROS) | 2016 | Prior physical path-loss model regularises the GP RSSI map. | Use physics to tame sparse data. |
| Arun et al., *P2SLAM: Bearing-Based WiFi SLAM for Indoor Robots* (ICRA) | 2022 | Two-way **CSI bearings** from AP and robot give unique SLAM measurements. | Requires CSI. **Not possible on ESP8266**; notes RSSI is too unstable for bearing. |
| Kim et al., *Structure from WiFi (SfW): RSSI-based Geometric Mapping of Indoor Environments* (arXiv 2403.02235) | 2024 | Inverse k-visibility: with known router position and a trajectory, RSSI->k thresholds mark walls where consecutive k-regions meet; builds an occupancy grid. | The frontier for "map surroundings from radio". We can implement a scaled-down version. Explicitly RSSI-only, no camera/lidar. |
| *Autonomous WiFi Fingerprinting for Indoor Localization* (arXiv 1911.11825) | 2019 | SLAM robot builds fingerprint DB automatically; GP fits spatial RSSI, residual test flags anomalies. | Template for auto-surveying and anomaly detection. |
| Azghadi et al., *Adaptive Indoor Localization ... SLAM robot + DNN* (arXiv 2407.09242) | 2024 | Robot-guided fingerprint dataset -> DNN localization; 26% better than traditional. | Fingerprinting accuracy is bounded by data collection quality. |
| HGP-RL (arXiv 2307.10614) | 2023 | Hierarchical Gaussian processes map RSSI to a connected AP; robots locate AP and each other. | Shows GP RSSI maps run on constrained devices. |

## Existing open-source projects (closest first)

| Project | Stack | What it does | Reuse |
| --- | --- | --- | --- |
| `CoruHS/WiFi-Indoor-Positioning` | NodeMCU ESP8266 + Python | Firmware scans APs, filters, emits `AP:ssid|bssid|rssi|channel` frames; Python does walking surveys and kNN/MLP; ~2.3 m median error. | **Nearest twin to our plan.** Confirms the scan->serial->host pattern and the ~2 m RSSI jitter floor. |
| `efealtas/wifi-rssi-mapping` | Python | Guided corner-by-corner RSSI sampling, estimates router location, matplotlib map. | Survey UX ideas; data-driven router estimate. |
| `MahdiarHarandi/wifi-indoor-positioning` | ESP8266 anchors + central | Hyrid kNN fingerprinting + trilateration over 6 beacons. | Multi-node only; needs several boards. |
| `Aarav7162/rssi_location_triangulation` | ESP8266 anchors + Python | Anchors + soft-AP tag, 1-NN fingerprints, Blynk dashboard. | Multi-node. |
| `VaseSimion/ESP-RSSI` | ESP8266 | **Promiscuous mode** captures RSSI of packets from other ESPs. | Shows the high-rate sniffer path that scans cannot give us. |
| `espressif/esp-csi` | ESP32 family | CSI-based sensing (amplitude/phase). | Not usable on ESP8266; documents the capability gap. |

## What this means for a single ESP8266

1. **The board can do the sensing.** RSSI scanning and promiscuous sniffing both
   work on ESP8266; CSI does not. So the mapping modality is RSSI only.
2. **Fingerprinting is proven end-to-end on exactly this board.** We can stand on
   `CoruHS`'s shoulders for the pipeline and spend our effort on the mapping
   geometry instead.
3. **RSSI jitter sets the accuracy ceiling** (~2 m for static fingerprints).
   Anything better needs temporal averaging or a faster sampler - which is where
   the promiscuous sniffer earns its place.
4. **Geometric mapping from RSSI is real but young.** SfW + Fafoutis's k-means
   wall thresholding are implementable here and are our differentiator.
5. **One radio means time-division, not simultaneity.** We cannot be AP and STA
   on two channels at once; a single board can scan ambient APs, or sniff one
   chosen transmitter, but not both continuously.

## Design consequence

Build three layers on the same firmware/host spine:

1. **Fingerprint map** (safe, proven): labelled RSSI grid -> heatmaps + kNN/GP
   localization with honest error metrics.
2. **Wall geometry** (frontier): SfW-lite - k-means RSSI thresholds -> k values ->
   occupancy sketch, given a trajectory and a known reference transmitter.
3. **Dense RSSI motion stream** (enabler): promiscuous sniffer for fast samples,
   so a moving board produces a real time series instead of one value per 2 s.

See `architecture.md` for how these are wired.
