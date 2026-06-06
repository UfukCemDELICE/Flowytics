from pydantic import BaseModel

def clean_unicode_minus(val):
    if isinstance(val, str):
        return val.replace("\u2212", "-")
    elif isinstance(val, list):
        return [clean_unicode_minus(item) for item in val]
    elif isinstance(val, dict):
        return {k: clean_unicode_minus(v) for k, v in val.items()}
    elif isinstance(val, BaseModel):
        return val.model_copy(update={
            k: clean_unicode_minus(getattr(val, k))
            for k in val.__class__.model_fields
        })
    elif hasattr(val, "__dict__"):
        for k, v in list(val.__dict__.items()):
            setattr(val, k, clean_unicode_minus(v))
        return val
    return val
