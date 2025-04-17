# 🔄 Promock

Promock is a Prometheus mock exporter that generates synthetic but realistic metrics for testing dashboards and monitoring setups.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Docker Pulls](https://img.shields.io/badge/docker%20pulls-available-blue)
![Version](https://img.shields.io/badge/version-1.0.0-brightgreen)

## 📖 Overview

Promock learns from real Prometheus metric files (`.prom`) and generates synthetic metrics with realistic patterns and variations. Perfect for:

- Testing Grafana dashboards without production data
- Demonstrating monitoring setups to clients
- Training teams on monitoring workflows
- Developing alerting rules against simulated service behaviors

## ✨ Features

- **Learn from examples**: Place real `.prom` files in a directory and Promock analyzes their structure
- **Statistically accurate**: Generates values based on learned statistical distributions
- **Realistic behavior**:
  - Counters increment naturally over time
  - Gauges fluctuate within realistic ranges
  - Labels are preserved exactly as in sample data
- **Simple deployment**: Ready-to-use Docker container
- **Low overhead**: Lightweight implementation that won't slow down your testing environment
- **Auto-refresh**: Regularly re-scans for changes to `.prom` files

## 🚀 Quick Start

### Using Docker Compose (recommended)

```bash
# Clone the repository
git clone https://github.com/Liquescent-Development/promock.git
cd promock

# Start the container
docker-compose up -d

# Test it
curl http://localhost:9090/metrics
```

### Using Docker directly

```bash
# Build the Docker image
docker build -t promock .

# Run the container
docker run -p 9090:9090 -v $(pwd)/samples:/metrics promock
```

## 📊 Sample Output

```bash
# HELP http_requests_total Total number of HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="get",endpoint="/api/v1",status="200"} 1245.72
http_requests_total{method="get",endpoint="/api/v1",status="404"} 17.32
http_requests_total{method="get",endpoint="/api/v1",status="500"} 6.21
http_requests_total{method="post",endpoint="/api/v1",status="200"} 402.56
http_requests_total{method="post",endpoint="/api/v1",status="400"} 19.67
http_requests_total{method="post",endpoint="/api/v1",status="500"} 3.14

# HELP system_memory_usage_bytes Memory usage in bytes
# TYPE system_memory_usage_bytes gauge
system_memory_usage_bytes{type="free"} 3947322368
system_memory_usage_bytes{type="used"} 8926543872
system_memory_usage_bytes{type="cached"} 2314589184
```

## 🧩 How It Works

### Core Mechanism

1. **Parsing**: Analyzes `.prom` files to extract:
   - Metric names, types, and help text
   - Label dimensions
   - Value distributions (min, max, mean, standard deviation)

2. **Statistical Analysis**: Calculates:
   - Range limits for each metric
   - Standard deviation of values
   - Patterns for specific label combinations
   - Increment rates for counter metrics

3. **Generation**: When `/metrics` is called:
   - Counters: Increments existing values at realistic rates
   - Gauges: Generates new values following original distribution
   - All original structure and metadata is preserved

### Detailed Implementation

#### Learning Phase

```plaintext
┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│                   │     │                   │     │                   │
│  .prom Files      │────▶│  Metric Parser    │────▶│  Statistical      │
│                   │     │                   │     │  Analysis         │
└───────────────────┘     └───────────────────┘     └───────────────────┘
                                                             │
                                                             ▼
┌───────────────────┐                            ┌───────────────────┐
│                   │                            │                   │
│  Metric Generator │◀───────────────────────────│  Metric Models    │
│                   │                            │                   │
└───────────────────┘                            └───────────────────┘
```

1. **Metric Parser**:
   - Reads Prometheus exposition format
   - Extracts metadata (HELP, TYPE)
   - Extracts sample values and labels
   - Groups metrics by name and label combinations

2. **Statistical Analysis**:
   - For each metric + label combination:
     - Calculates min/max/mean/std dev
     - Detects if values are monotonically increasing (counters)
     - Models rate of change between samples
     - Identifies normal vs abnormal ranges

3. **Metric Models**:
   - Creates statistical models for each metric
   - Maintains separate models for different label combinations
   - Tracks counter state to ensure proper incrementing
   - Stores distribution parameters for gauges

#### Generation Phase

```plaintext
┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│                   │     │                   │     │                   │
│  Prometheus       │────▶│  /metrics         │────▶│  Model-based      │
│  Scrape           │     │  Endpoint         │     │  Generation       │
└───────────────────┘     └───────────────────┘     └───────────────────┘
                                                             │
                                                             ▼
┌───────────────────┐                            ┌───────────────────┐
│                   │                            │                   │
│  Prometheus       │◀───────────────────────────│  Synthetic        │
│  Storage          │                            │  Metrics          │
└───────────────────┘                            └───────────────────┘
```

1. **Model-based Generation**:
   - Counters:
     - Reads current counter state
     - Applies realistic increments based on learned rates
     - Updates counter state for next scrape
   - Gauges:
     - Generates values using normal distribution
     - Bounds values within min/max ranges
     - Applies learned correlation patterns

2. **Output Formatting**:
   - Preserves exact metric names and types
   - Maintains all original label dimensions
   - Follows Prometheus exposition format

### Algorithm Details

For **counter metrics**, Promock implements a time-series based increment model:

```python
# Simplified algorithm for counter increment
def generate_counter_increment(metric):
    if metric.std_dev and metric.std_dev > 0:
        # Use normal distribution based on observed changes
        increment = abs(random.gauss(metric.mean_increment, metric.std_dev))
    else:
        # Fallback to a reasonable default
        increment = random.uniform(0.1, 1.0)
    
    # Apply time adjustment
    time_since_last_scrape = current_time - last_scrape_time
    adjusted_increment = increment * (time_since_last_scrape / 60.0)  # Scale to per-minute rate
    
    return adjusted_increment
```

For **gauge metrics**, Promock uses a constrained random walk model:

```python
# Simplified algorithm for gauge generation
def generate_gauge_value(metric):
    if metric.std_dev and metric.std_dev > 0 and metric.mean_value is not None:
        # Generate normally distributed value using observed statistics
        value = random.gauss(metric.mean_value, metric.std_dev)
        # Constrain to min/max range with dampening to avoid wild swings
        value = current_value + (value - current_value) * dampening_factor
        # Final clamping to observed range
        value = max(min(value, metric.max_value), metric.min_value)
    else:
        # Fallback to uniform distribution
        value = random.uniform(metric.min_value, metric.max_value)
    
    return value
```

### Performance Optimizations

1. **Caching**: Metrics definitions are cached and only refreshed periodically
2. **Efficient Label Handling**: Labels are stored as sorted string keys for fast lookup
3. **Incremental Updates**: Only changed files are re-parsed during directory scans
4. **Lazy Loading**: Statistical models are only computed when needed

## 📁 Creating Sample Metrics

### Basic Sample Collection

The easiest way to create sample metrics is to scrape them from an existing Prometheus exporter:

```bash
# Basic metrics capture
curl http://your-exporter:port/metrics > service_name.prom
```

Place this file in the `samples/` directory.

### Time-Series Learning

For more realistic metrics generation, Promock can **learn from time-series data**. Collect multiple samples of the same service at different points in time:

```bash
# Collect samples every minute for 5 minutes
for i in {1..5}; do
  curl http://your-exporter:port/metrics > service_name_$(date +%s).prom
  echo "Collected sample $i"
  sleep 60
done
```

**How Time-Series Learning Works:**

1. When multiple samples of the same metrics exist, Promock analyzes the **pattern of change** between samples
2. For counter metrics:
   - Calculates the **rate of increase** between samples
   - Learns the **statistical distribution** of these increments (mean, variability)
   - Generates new values that increase at similar rates to real data

3. For gauge metrics:
   - Learns the **range of fluctuation** over time
   - Identifies **patterns** in how metrics move up and down
   - Models the **correlation** between related metrics when possible

**Example:**

If your samples show `http_requests_total{endpoint="/login"}` increasing:

- Sample 1: 1000 requests
- Sample 2 (5 min later): 1240 requests
- Sample 3 (5 min later): 1510 requests

Promock learns this counter increases by ~45-55 requests per minute with some variability.

When serving metrics:

- First scrape: 1510 requests (starting from last sample)
- Second scrape (1 min later): ~1560 requests
- Third scrape (1 min later): ~1615 requests

This creates much more realistic dashboards as the **rate of change** matches your real services.

Place all these sample files in the `samples/` directory.

## 🖥️ Grafana Integration

1. Configure Prometheus as a data source in Grafana
2. Create dashboards using metrics from Promock
3. Watch as your dashboards display realistic, ever-changing data

## 💡 Use Cases

### Dashboard Development

Test and refine dashboards with realistic data patterns before deploying to production.

### Demos & Presentations

Showcase monitoring capabilities with representative metrics that change over time.

### Training

Teach team members about Prometheus and Grafana without needing access to production systems.

### CI/CD Testing

Validate monitoring components, alert rules, and dashboard functionality in your CI pipeline.

## 📚 Advanced Usage

### Multiple Service Simulation

To simulate multiple services, create separate `.prom` files for each:

``` bash
samples/
  ├── api_service.prom
  ├── database.prom
  ├── cache.prom
  └── user_service.prom
```

### Learning from Production Patterns

Promock can learn sophisticated patterns from production metrics. Here's how to leverage this capability:

#### 1. Capturing Temporal Patterns

Collect metrics from your production system at different times:

```bash
# Morning sample
curl http://prod-exporter/metrics > service_morning.prom

# Afternoon peak
curl http://prod-exporter/metrics > service_peak.prom

# Evening sample
curl http://prod-exporter/metrics > service_evening.prom

# Weekend sample
curl http://prod-exporter/metrics > service_weekend.prom
```

Promock will analyze these samples and generate metrics that reflect all of these patterns.

#### 2. Capturing Growth and Decay Patterns

For metrics that show predictable growth or decay:

```bash
# Initial state (e.g., after service restart)
curl http://service-exporter/metrics > service_initial.prom

# Warmup period
curl http://service-exporter/metrics > service_warmup.prom

# Steady state
curl http://service-exporter/metrics > service_steady.prom

# High load
curl http://service-exporter/metrics > service_high_load.prom
```

Promock will learn how metrics evolve through these states.

#### 3. Capturing Error States

Include samples with error conditions:

```bash
# Normal operation
curl http://service-exporter/metrics > service_normal.prom

# During degraded performance
curl http://service-exporter/metrics > service_degraded.prom

# During error state
curl http://service-exporter/metrics > service_error.prom

# During recovery
curl http://service-exporter/metrics > service_recovery.prom
```

This teaches Promock about the correlation between error counters, latency metrics, and other indicators.

#### Understanding the Learning Mechanism

When Promock encounters multiple samples of the same metric, it:

1. **Computes value deltas**: For each unique metric+label combination, it calculates how much the value changed between samples
2. **Builds a statistical model**: It develops a probability distribution of these changes
3. **Applies temporal context**: If the samples include timestamps, it can model rate-of-change over time
4. **Preserves correlations**: It maintains relationships between related metrics that change together

For counters, this means generating realistic increment rates rather than random jumps. For gauges, it means realistic fluctuations within observed ranges.

#### Customizing Learning Behavior

Place your sample files in subdirectories to represent different scenarios:

```bash
samples/
  ├── normal/
  │   ├── service_1.prom
  │   ├── service_2.prom
  │   └── service_3.prom
  ├── high_load/
  │   ├── service_high_1.prom
  │   ├── service_high_2.prom
  │   └── service_high_3.prom
  └── error/
      ├── service_error_1.prom
      ├── service_error_2.prom
      └── service_error_3.prom
```

Then create symbolic links to the scenario you want to simulate:

```bash
ln -sf normal/* samples/
# or
ln -sf high_load/* samples/
# or
ln -sf error/* samples/
```

And restart Promock to apply the new scenario.

### Running the Full Stack

```bash
# Start the entire monitoring stack
docker-compose up -d
```

### Accessing the Components

- **Promock**: <http://localhost:9090/metrics>
- **Prometheus**: <http://localhost:9091/>
- **Grafana**: <http://localhost:3000/> (login with admin/admin)

### Configuring Grafana

1. **Add Prometheus as a data source**:
   - Go to: Configuration > Data Sources > Add data source
   - Select: Prometheus
   - URL: `http://prometheus:9090`
   - Click: Save & Test

2. **Create a dashboard**:
   - Go to: Create > Dashboard
   - Add a new panel
   - In the query editor, select your Prometheus data source
   - Start typing a metric name (they'll appear in the dropdown)
   - You can use functions like `rate()` for counters

### Example Queries

- Basic counter visualization:

  ```bash
  rate(http_requests_total{method="get"}[1m])
  ```

- Memory usage:

  ```bash
  system_memory_usage_bytes{type="used"} / (system_memory_usage_bytes{type="used"} + system_memory_usage_bytes{type="free"})
  ```

### Sample Dashboard JSON

You can import a sample dashboard to get started. From the Grafana UI, go to Dashboard > Import and paste [sample-dashboard.json](./json/sample-dashboard.json) into the text box.

### Creating Custom Dashboards

With this setup, you can:

1. Design and test dashboards with realistic data patterns
2. Experiment with alerting rules
3. Test visualization types and panel configurations
4. Develop dashboard templates for future production use

### Troubleshooting

- **No metrics showing in Grafana**: Verify Prometheus can scrape Promock by checking the Prometheus UI's "Targets" section
- **Incorrect metric types**: Make sure your sample `.prom` files have proper `# TYPE` metadata
- **Container connection issues**: Check that service names match in `docker-compose.yml` and `prometheus.yml`

## 🛠️ Development

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (for containerized deployment)

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the exporter
python exporter.py
```

### Running Tests

```bash
python -m unittest discover tests
```

## 📝 License

This project is licensed under the MIT License - see below for details:

```text
MIT License

Copyright (c) 2025 Liquescent Development LLC

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## 👥 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📣 Acknowledgments

- Inspired by the need for realistic test data in monitoring environments
- Thanks to the Prometheus community for the excellent exposition format
