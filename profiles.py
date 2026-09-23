"""Validated, immutable-per-review formatting profiles."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

Font = Literal['Arial', 'Times New Roman', 'Calibri', 'Cambria', 'Aptos']


class FormattingProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    name: str = Field(default='ADF default', min_length=1, max_length=80)
    source_note: str = Field(default='Existing project rules; verify against your department handbook.', max_length=250)
    body_font: Font = 'Arial'
    body_size: float = Field(default=12, ge=8, le=24)
    heading_size: float = Field(default=12, ge=8, le=28)
    caption_font: Font = 'Arial'
    caption_size: float = Field(default=11, ge=8, le=20)
    header_font: Font = 'Arial'
    header_size: float = Field(default=9, ge=8, le=16)
    line_spacing: float = Field(default=1.5, ge=1, le=3)
    margin_top: float = Field(default=1, ge=0.25, le=2)
    margin_bottom: float = Field(default=1, ge=0.25, le=2)
    margin_left: float = Field(default=1, ge=0.25, le=2)
    margin_right: float = Field(default=1, ge=0.25, le=2)
    required_sections: list[Literal['Abstract', 'Introduction', 'Literature review', 'Methodology', 'Results', 'Discussion', 'Conclusion', 'References']] = Field(
        default_factory=lambda: ['Abstract', 'Introduction', 'Methodology', 'Results', 'Conclusion', 'References'], max_length=8)


DEFAULT_PROFILE = FormattingProfile()
CORRECTION_GROUPS = ('fonts', 'sizes', 'spacing', 'margins', 'headers')


def profile_value(value=None):
    return value if isinstance(value, FormattingProfile) else FormattingProfile.model_validate(value or {})


def expected_typography(paragraph, profile):
    from utilities.formatting import is_caption
    if is_caption(paragraph):
        return profile.caption_font, profile.caption_size
    return profile.body_font, profile.heading_size if paragraph.style.name.startswith('Heading') else profile.body_size
