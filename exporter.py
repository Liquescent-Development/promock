import os
import re
import time
import random
import logging
import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Tuple
from flask import Flask, Response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mock-exporter')

@dataclass
class MetricSample:
    """Represents a single sample value of a metric"""
    value: float
    labels: Dict[str, str] = None
    
    def __post_init__(self):
        if self.labels is None:
            self.labels = {}

@dataclass
class MetricDefinition:
    """Represents a Prometheus metric with its metadata and samples"""
    name: str
    metric_type: str
    help_text: str
    samples: List[MetricSample]
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    std_dev: Optional[float] = None
    is_counter: bool = False
    
    def __post_init__(self):
        # Calculate statistics for the metric values
        if self.samples:
            values = [sample.value for sample in self.samples]
            self.min_value = min(values)
            self.max_value = max(values)
            self.mean_value = statistics.mean(values)
            if len(values) > 1:
                self.std_dev = statistics.stdev(values)
            else:
                self.std_dev = 0
                
        # Determine if it's a counter based on type
        self.is_counter = self.metric_type.lower() == 'counter'

class PrometheusFileParser:
    """Parses .prom files containing Prometheus metrics"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.metrics: Dict[str, MetricDefinition] = {}
        
    def parse(self) -> Dict[str, MetricDefinition]:
        """Parse the .prom file and return the metrics found"""
        logger.info(f"Parsing file: {self.file_path}")
        
        with open(self.file_path, 'r') as f:
            content = f.read()
            
        lines = content.strip().split('\n')
        current_metric = None
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                # Skip empty lines or process metadata
                if line.startswith('# HELP '):
                    parts = line[len('# HELP '):].split(' ', 1)
                    if len(parts) == 2:
                        name, help_text = parts
                        if name not in self.metrics:
                            self.metrics[name] = MetricDefinition(
                                name=name,
                                metric_type='',
                                help_text=help_text,
                                samples=[]
                            )
                            current_metric = name
                        else:
                            self.metrics[name].help_text = help_text
                
                elif line.startswith('# TYPE '):
                    parts = line[len('# TYPE '):].split(' ', 1)
                    if len(parts) == 2:
                        name, metric_type = parts
                        if name not in self.metrics:
                            self.metrics[name] = MetricDefinition(
                                name=name,
                                metric_type=metric_type,
                                help_text='',
                                samples=[]
                            )
                            current_metric = name
                        else:
                            self.metrics[name].metric_type = metric_type
            else:
                # Process metric sample
                # Format: name{label="value",...} value [timestamp]
                # or: name value [timestamp]
                metric_pattern = r'([a-zA-Z_:][a-zA-Z0-9_:]*)'  # Metric name
                labels_pattern = r'(?:{(.*?)})?'  # Optional labels
                value_pattern = r'([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)'  # Value
                timestamp_pattern = r'(?: (\d+))?'  # Optional timestamp
                
                pattern = f'^{metric_pattern}{labels_pattern} {value_pattern}{timestamp_pattern}$'
                match = re.match(pattern, line)
                
                if match:
                    name = match.group(1)
                    labels_str = match.group(2)
                    value = float(match.group(3))
                    
                    # Parse labels if present
                    labels = {}
                    if labels_str:
                        label_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)="(.*?)"'
                        for label_match in re.finditer(label_pattern, labels_str):
                            label_name, label_value = label_match.groups()
                            labels[label_name] = label_value
                    
                    # Add or update metric
                    if name not in self.metrics:
                        self.metrics[name] = MetricDefinition(
                            name=name,
                            metric_type='',
                            help_text='',
                            samples=[]
                        )
                    
                    self.metrics[name].samples.append(MetricSample(value=value, labels=labels))
        
        # Post-process metrics to calculate statistics
        for name, metric in self.metrics.items():
            if hasattr(metric, '__post_init__'):
                metric.__post_init__()
        
        return self.metrics

class MetricGenerator:
    """Generates synthetic metrics based on parsed metric definitions"""
    
    def __init__(self, metrics_dir: str):
        self.metrics_dir = metrics_dir
        self.metrics: Dict[str, MetricDefinition] = {}
        self.counter_state: Dict[str, Dict[str, float]] = {}  # Stores state for counters
        self.scan_interval = 60  # Rescan directory every 60 seconds
        self.last_scan_time = 0
        
    def scan_directory(self) -> None:
        """Scan directory for .prom files and parse metrics"""
        current_time = time.time()
        
        # Only rescan if enough time has passed
        if current_time - self.last_scan_time < self.scan_interval:
            return
            
        logger.info(f"Scanning directory: {self.metrics_dir}")
        self.last_scan_time = current_time
        
        # Temporary metrics storage to avoid race conditions
        new_metrics = {}
        
        try:
            for filename in os.listdir(self.metrics_dir):
                if filename.endswith('.prom'):
                    file_path = os.path.join(self.metrics_dir, filename)
                    parser = PrometheusFileParser(file_path)
                    file_metrics = parser.parse()
                    
                    # Merge metrics from this file
                    for name, metric in file_metrics.items():
                        if name in new_metrics:
                            # Combine samples if metric already exists
                            new_metrics[name].samples.extend(metric.samples)
                        else:
                            new_metrics[name] = metric
            
            # Replace metrics dictionary with new data
            self.metrics = new_metrics
            
            # Initialize counter state for new metrics
            for name, metric in self.metrics.items():
                if metric.is_counter and name not in self.counter_state:
                    self.counter_state[name] = {}
                    
                    # Initialize counter state for each unique label combination
                    for sample in metric.samples:
                        label_key = self._labels_to_key(sample.labels)
                        if label_key not in self.counter_state[name]:
                            # Start counters at a value within the observed range
                            if metric.min_value is not None and metric.max_value is not None:
                                start_value = random.uniform(metric.min_value, metric.max_value)
                                self.counter_state[name][label_key] = start_value
        
        except Exception as e:
            logger.error(f"Error scanning directory: {e}")
    
    def _labels_to_key(self, labels: Dict[str, str]) -> str:
        """Convert labels dictionary to a string key"""
        if not labels:
            return ""
        
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
    
    def _key_to_labels(self, key: str) -> Dict[str, str]:
        """Convert a string key back to labels dictionary"""
        if not key:
            return {}
        
        labels = {}
        for item in key.split(","):
            if "=" in item:
                k, v = item.split("=", 1)
                labels[k] = v
        
        return labels
    
    def generate_metrics(self) -> str:
        """Generate synthetic metrics based on parsed definitions"""
        self.scan_directory()
        
        if not self.metrics:
            return "# No metrics found\n"
        
        output = []
        
        for name, metric in sorted(self.metrics.items()):
            # Add metadata
            if metric.help_text:
                output.append(f"# HELP {name} {metric.help_text}")
            if metric.metric_type:
                output.append(f"# TYPE {name} {metric.metric_type}")
            
            # Group samples by unique label combinations
            label_groups = {}
            for sample in metric.samples:
                label_key = self._labels_to_key(sample.labels)
                if label_key not in label_groups:
                    label_groups[label_key] = []
                label_groups[label_key].append(sample.value)
            
            # Generate a synthetic value for each label combination
            for label_key, values in label_groups.items():
                labels = self._key_to_labels(label_key)
                
                if metric.is_counter:
                    # For counters, we need to ensure they always increase
                    if name in self.counter_state and label_key in self.counter_state[name]:
                        # Get the current counter value
                        current_value = self.counter_state[name][label_key]
                        
                        # Generate an increment based on the observed data
                        if metric.std_dev and metric.std_dev > 0:
                            # Use standard deviation to determine increment
                            increment = abs(random.gauss(0, metric.std_dev))
                        else:
                            # Fallback to a small random increment
                            increment = random.uniform(0.1, 1.0)
                        
                        # Update the counter
                        new_value = current_value + increment
                        self.counter_state[name][label_key] = new_value
                        
                        # Format the output line
                        if labels:
                            labels_str = "{" + ",".join(f'{k}="{v}"' for k, v in labels.items()) + "}"
                            output.append(f"{name}{labels_str} {new_value}")
                        else:
                            output.append(f"{name} {new_value}")
                else:
                    # For gauges and other metric types, generate a value within the observed range
                    if metric.min_value is not None and metric.max_value is not None:
                        if metric.std_dev and metric.std_dev > 0 and metric.mean_value is not None:
                            # Generate normally distributed values using observed statistics
                            value = random.gauss(metric.mean_value, metric.std_dev)
                            # Clamp to min/max range
                            value = max(min(value, metric.max_value), metric.min_value)
                        else:
                            # Fallback to uniform distribution
                            value = random.uniform(metric.min_value, metric.max_value)
                        
                        # Format the output line
                        if labels:
                            labels_str = "{" + ",".join(f'{k}="{v}"' for k, v in labels.items()) + "}"
                            output.append(f"{name}{labels_str} {value}")
                        else:
                            output.append(f"{name} {value}")
        
        return "\n".join(output) + "\n"

app = Flask(__name__)
metrics_generator = None

@app.route('/metrics')
def metrics():
    """Endpoint for Prometheus to scrape metrics"""
    if metrics_generator:
        return Response(metrics_generator.generate_metrics(), mimetype='text/plain')
    return Response("# No metrics found\n", mimetype='text/plain')

@app.route('/health')
def health():
    """Health check endpoint"""
    return Response("OK", mimetype='text/plain')

def main():
    """Main entry point"""
    global metrics_generator
    
    metrics_dir = os.environ.get('METRICS_DIR', '/metrics')
    port = int(os.environ.get('PORT', 9090))
    
    logger.info(f"Starting Prometheus Mock Exporter on port {port}")
    logger.info(f"Monitoring directory: {metrics_dir}")
    
    metrics_generator = MetricGenerator(metrics_dir)
    
    # Initial scan
    metrics_generator.scan_directory()
    
    # Start Flask app
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    main()