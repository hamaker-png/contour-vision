from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Box(StrictModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def inside_image(self):
        if self.x + self.width > 1.00001 or self.y + self.height > 1.00001:
            raise ValueError("A box must fit inside its image")
        return self


class Sample(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(max_length=200)
    data: str = Field(max_length=12_000_000)
    split: Literal["train", "validation"] = "train"
    labeled: bool = False
    boxes: list[Box] = Field(default_factory=list, max_length=150)


class Measurements(StrictModel):
    fields: list[Literal["length", "width", "area", "angle", "color", "center"]] = Field(
        default_factory=lambda: ["length", "width", "color"]
    )
    pixels_per_unit: float = Field(default=0, ge=0, le=1_000_000)
    unit: Literal["mm", "cm", "in"] = "mm"


class Strategy(StrictModel):
    name: str = Field(min_length=1, max_length=100)
    method: Literal["hsv", "otsu", "adaptive", "canny"]
    rationale: str = Field(default="", max_length=2000)
    hue_low: int = Field(default=0, ge=0, le=179)
    hue_high: int = Field(default=179, ge=0, le=179)
    saturation_low: int = Field(default=50, ge=0, le=255)
    saturation_high: int = Field(default=255, ge=0, le=255)
    value_low: int = Field(default=30, ge=0, le=255)
    value_high: int = Field(default=255, ge=0, le=255)
    invert: bool = False
    blur: int = Field(default=3, ge=1, le=15)
    morph: int = Field(default=3, ge=0, le=15)
    block_size: int = Field(default=31, ge=3, le=101)
    adaptive_c: float = Field(default=5, ge=-40, le=40)
    canny_low: int = Field(default=50, ge=0, le=254)
    canny_high: int = Field(default=150, ge=1, le=255)
    min_area: float = Field(default=0.001, ge=0.00001, le=0.9)
    max_area: float = Field(default=0.85, gt=0, le=1)
    min_circularity: float = Field(default=0, ge=0, le=1)
    min_solidity: float = Field(default=0, ge=0, le=1)
    min_aspect: float = Field(default=1, ge=1, le=100)
    max_aspect: float = Field(default=100, ge=1, le=100)
    reject_border: bool = True

    @model_validator(mode="after")
    def valid_ranges(self):
        for low, high in [(self.min_area, self.max_area), (self.min_aspect, self.max_aspect),
                          (self.saturation_low, self.saturation_high), (self.value_low, self.value_high),
                          (self.canny_low, self.canny_high)]:
            if low > high:
                raise ValueError("A lower bound must not exceed its upper bound")
        if self.blur % 2 != 1 or self.block_size % 2 != 1:
            raise ValueError("Blur and adaptive block size must be odd")
        return self


class AnalyzeRequest(StrictModel):
    samples: list[Sample] = Field(min_length=1, max_length=12)
    description: str = Field(min_length=3, max_length=6000)
    context: str = Field(default="", max_length=6000)
    answers: str = Field(default="", max_length=6000)
    measurements: Measurements = Field(default_factory=Measurements)
    model: str = Field(default="gpt-4.1", min_length=1, max_length=100)


class DiscoveryRequest(AnalyzeRequest):
    # Image-first discovery can ask the user what matters before a target is named.
    description: str = Field(default="", max_length=6000)

    @model_validator(mode="after")
    def unique_images(self):
        if len({s.id for s in self.samples}) != len(self.samples):
            raise ValueError("Image IDs must be unique")
        return self


class ExperimentRequest(StrictModel):
    samples: list[Sample] = Field(min_length=1, max_length=12)
    strategies: list[Strategy] = Field(min_length=1, max_length=6)
    measurements: Measurements = Field(default_factory=Measurements)
    tune: bool = True


class ExportRequest(StrictModel):
    strategy: Strategy
    measurements: Measurements = Field(default_factory=Measurements)
    description: str = Field(default="Object detector", max_length=6000)
