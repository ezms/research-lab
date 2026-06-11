"""Subprocess entry point for running research pipelines without Qt state."""
import importlib
import json
import sys


def main() -> None:
    payload = json.loads(sys.stdin.read())
    module_path, class_name = payload["manifest"].rsplit(":", 1)

    mod = importlib.import_module(module_path)
    manifest_cls = getattr(mod, class_name)
    params = manifest_cls.params_model.model_validate(payload["params"])
    result = manifest_cls().run(params)

    output = {
        uf: {ft: str(path) for ft, path in files.items()}
        for uf, files in result.items()
    }
    sys.stdout.write(json.dumps(output))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
