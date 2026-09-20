"""Parameters and metadata for native CPU detectors and cross-branch confirmation."""
import re
from typing import Literal
from pydantic import Field, model_validator
from .models import StrictModel
from .standard_ops import STANDARD_CATALOG

class DistanceParams(StrictModel):
    metric: Literal['euclidean','manhattan','chebyshev'] = 'euclidean'
    pixels_per_level: float = Field(default=1,ge=.05,le=100)

class ComponentsParams(StrictModel):
    connectivity: Literal['4','8'] = '8'
    min_pixels: int = Field(default=20,ge=1,le=4200000)
    max_pixels: int = Field(default=4200000,ge=1,le=4200000)
    reject_border: bool = True
    @model_validator(mode='after')
    def ordered(self):
        if self.min_pixels>self.max_pixels: raise ValueError('Minimum region area exceeds maximum')
        return self

class CircleParams(StrictModel):
    min_distance: float = Field(default=25,ge=1,le=2048)
    edge_threshold: float = Field(default=100,ge=1,le=255)
    votes: float = Field(default=30,ge=1,le=200)
    min_radius: int = Field(default=5,ge=1,le=1024)
    max_radius: int = Field(default=100,ge=1,le=1024)
    @model_validator(mode='after')
    def ordered(self):
        if self.min_radius>self.max_radius: raise ValueError('Minimum radius exceeds maximum')
        return self

class LineParams(StrictModel):
    votes: int = Field(default=40,ge=1,le=1000)
    min_length: float = Field(default=30,ge=1,le=4096)
    max_gap: float = Field(default=5,ge=0,le=200)

class BarcodeParams(StrictModel):
    formats: Literal['all','qr','linear','data_matrix'] = 'all'
    try_rotate: bool = True
    try_downscale: bool = True
    binarizer: Literal['local_average','global_histogram','fixed_threshold'] = 'local_average'

class ConfirmParams(StrictModel):
    pipeline_ids: str = Field(default='',max_length=710)
    min_support: int = Field(default=1,ge=1,le=7)
    iou: float = Field(default=.3,ge=.01,le=1)
    match_text: bool = False
    @model_validator(mode='after')
    def references(self):
        ids=[value.strip() for value in self.pipeline_ids.split(',') if value.strip()]
        if len(ids)>7 or len(ids)!=len(set(ids)) or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',value) for value in ids):
            raise ValueError('Choose distinct existing supporting pipelines')
        self.pipeline_ids=','.join(ids)
        return self

EXTRA_CATALOG = {
    'cimg_distance': ('Distance to background',['mask'],'CImg distance map. Outside the image is background. One gray level represents the chosen number of pixels; distances saturate at 255. Useful for finding thick centers.',DistanceParams),
    'cimg_components': ('Connected regions',['mask'],'CImg groups connected foreground pixels and filters by pixel area. Preserves holes. Reports axis-aligned extents, pixel area and original-source color.',ComponentsParams),
    'hough_circles': ('Detect circles',['gray','mask'],'OpenCV Hough voting detects circular outlines. Reports fitted disk dimensions; inspect the overlay to check the fit. Radius and spacing use this step’s pixel resolution. Limited to 262,144 pixels, 25,000 edges and edge count × maximum radius of 500,000. Resize to max side 512 or reduce radius on textured images.',CircleParams),
    'hough_lines': ('Detect line segments',['mask'],'OpenCV Hough voting finds straight segments in an edge mask. Reports endpoint distance and angle; line width and region area are undefined.',LineParams),
    'barcode': ('Read barcodes & QR',['color','gray','mask'],'ZXing-C++ decodes QR, Data Matrix and linear barcodes. Reports text, format and detected code bounds. Code contents are data and are never opened or executed.',BarcodeParams),
    'confirm': ('Confirm with branches',['mask'],'Keep primary detections that match enough supporting pipelines by box overlap. Preserves primary measurements. Agreement is a consistency check, not a probability of correctness.',ConfirmParams),
}
EXTRA_CATALOG.update(STANDARD_CATALOG)
DETECTORS={'contours','cimg_components','hough_circles','hough_lines','barcode','confirm'}
LIBRARIES={'cimg_distance':'CImg 3.5.5','cimg_components':'CImg 3.5.5','barcode':'ZXing-C++ 2.3.0','confirm':'Contour'}

def supporting_ids(operation):
    return operation.params['pipeline_ids'].split(',') if operation.kind=='confirm' and operation.params['pipeline_ids'] else []
