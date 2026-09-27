use pyo3::{
    exceptions::PyValueError,
    prelude::{pyclass, pymethods, pymodule, Bound, Py, PyModule, PyResult, Python},
    types::PyModuleMethods,
};

use crate::simulation::{EngineCommand, Simulator};

#[pyclass(name = "Simulator")]
pub struct PySimulator {
    inner: Simulator,
}

#[pymethods]
impl PySimulator {
    #[new]
    fn new() -> Self {
        Self {
            inner: Simulator::new(),
        }
    }

    fn apply(&mut self, command_json: &str) -> PyResult<String> {
        let command: EngineCommand = serde_json::from_str(command_json)
            .map_err(|error| PyValueError::new_err(format!("命令解析失败：{error}")))?;
        let snapshot = self
            .inner
            .apply(command)
            .map_err(|error| PyValueError::new_err(error.to_string()))?;
        serde_json::to_string(&snapshot)
            .map_err(|error| PyValueError::new_err(format!("状态序列化失败：{error}")))
    }

    fn snapshot(&self) -> PyResult<String> {
        serde_json::to_string(&self.inner.snapshot())
            .map_err(|error| PyValueError::new_err(format!("状态序列化失败：{error}")))
    }

    fn apply_native(
        &mut self,
        py: Python<'_>,
        command_json: &str,
    ) -> PyResult<Py<pyo3::types::PyDict>> {
        let command: EngineCommand = serde_json::from_str(command_json)
            .map_err(|error| PyValueError::new_err(format!("命令解析失败：{error}")))?;
        self.inner
            .execute(command)
            .map_err(|error| PyValueError::new_err(error.to_string()))?;
        crate::python_snapshot::snapshot(py, &self.inner)
    }
}

#[pymodule]
fn mcscai_engine(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PySimulator>()?;
    module.add_function(pyo3::wrap_pyfunction!(
        crate::python_preflight::generator_preflight,
        module
    )?)?;
    module.add("__generator_api__", 1)?;
    module.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
