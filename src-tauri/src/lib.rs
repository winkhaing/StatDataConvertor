use serde::Deserialize;
use serde_json::{json, Value};
#[cfg(debug_assertions)]
use std::path::PathBuf;
use tauri::async_runtime::{Mutex, Receiver};
use tauri::{AppHandle, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ConversionRequest {
    input_path: String,
    output_path: String,
    input_format: Option<String>,
    output_format: Option<String>,
    #[serde(default)]
    input_options: Value,
    #[serde(default)]
    output_options: Value,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ValidationRequest {
    input_path: String,
    target_format: String,
    artifact_directory: Option<String>,
    input_format: Option<String>,
    #[serde(default)]
    input_options: Value,
    #[serde(default)]
    output_options: Value,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct BridgeInstallRequest {
    manifest_path: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CertificationAuditRequest {
    manifest_path: String,
}

#[cfg(debug_assertions)]
fn development_engine_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("src-tauri must have a project parent")
        .join("engine")
}

#[cfg(debug_assertions)]
fn development_python() -> String {
    if let Ok(configured) = std::env::var("STATDATA_ENGINE_PYTHON") {
        return configured;
    }
    let engine_dir = development_engine_dir();
    let candidates = if cfg!(windows) {
        vec![
            engine_dir.join(".venv").join("Scripts").join("python.exe"),
            engine_dir.join(".venv").join("Scripts").join("python3.exe"),
        ]
    } else {
        vec![
            engine_dir.join(".venv").join("bin").join("python3"),
            engine_dir.join(".venv").join("bin").join("python"),
        ]
    };
    candidates
        .into_iter()
        .find(|candidate| candidate.is_file())
        .map(|candidate| candidate.to_string_lossy().into_owned())
        .unwrap_or_else(|| "python3".to_string())
}

struct EngineProcess {
    child: CommandChild,
    events: Receiver<CommandEvent>,
}

#[derive(Default)]
struct EngineState {
    process: Mutex<Option<EngineProcess>>,
}

fn engine_command(app: &AppHandle) -> Result<tauri_plugin_shell::process::Command, String> {
    #[cfg(debug_assertions)]
    let command = {
        app.shell()
            .command(development_python())
            .args(["-m", "statdata_converter", "serve"])
            .env("PYTHONPATH", development_engine_dir().join("src"))
            .current_dir(development_engine_dir())
    };

    #[cfg(not(debug_assertions))]
    let command = app
        .shell()
        .sidecar("statdata-engine")
        .map_err(|error| format!("The bundled conversion engine is unavailable: {error}"))?
        .arg("serve");

    Ok(command)
}

async fn run_engine(
    app: &AppHandle,
    state: &EngineState,
    method: &str,
    params: Value,
) -> Result<Value, String> {
    let mut guard = state.process.lock().await;
    if guard.is_none() {
        let (events, child) = engine_command(app)?
            .spawn()
            .map_err(|error| format!("Could not start the local conversion engine: {error}"))?;
        *guard = Some(EngineProcess { child, events });
    }

    let process = guard
        .as_mut()
        .expect("the conversion engine was initialized");
    let request = json!({"id": 1, "method": method, "params": params});
    let mut encoded = serde_json::to_vec(&request)
        .map_err(|error| format!("Could not encode the conversion request: {error}"))?;
    encoded.push(b'\n');
    process
        .child
        .write(&encoded)
        .map_err(|error| format!("Could not contact the local conversion engine: {error}"))?;

    let mut stderr = Vec::new();
    while let Some(event) = process.events.recv().await {
        match event {
            CommandEvent::Stdout(line) => {
                let response: Value = serde_json::from_slice(&line).map_err(|error| {
                    format!("The conversion engine returned invalid data: {error}")
                })?;
                if let Some(message) = response.get("error").and_then(Value::as_str) {
                    return Err(message.to_string());
                }
                return response
                    .get("result")
                    .cloned()
                    .ok_or_else(|| "The conversion engine returned no result.".to_string());
            }
            CommandEvent::Stderr(line) => stderr.extend(line),
            CommandEvent::Error(message) => return Err(message),
            CommandEvent::Terminated(_) => {
                let detail = String::from_utf8_lossy(&stderr).trim().to_string();
                *guard = None;
                return Err(if detail.is_empty() {
                    "The local conversion engine stopped unexpectedly.".to_string()
                } else {
                    detail
                });
            }
            _ => {}
        }
    }
    *guard = None;
    Err("The local conversion engine closed its output stream.".to_string())
}

#[tauri::command]
async fn engine_capabilities(
    app: AppHandle,
    state: State<'_, EngineState>,
) -> Result<Value, String> {
    run_engine(&app, &state, "capabilities", json!({})).await
}

#[tauri::command]
async fn bridge_diagnostics(
    app: AppHandle,
    state: State<'_, EngineState>,
) -> Result<Value, String> {
    run_engine(&app, &state, "bridge_diagnostics", json!({})).await
}

#[tauri::command]
async fn install_bridge(
    app: AppHandle,
    state: State<'_, EngineState>,
    request: BridgeInstallRequest,
) -> Result<Value, String> {
    run_engine(
        &app,
        &state,
        "install_bridge",
        json!({"manifest_path": request.manifest_path}),
    )
    .await
}

#[tauri::command]
async fn audit_certification(
    app: AppHandle,
    state: State<'_, EngineState>,
    request: CertificationAuditRequest,
) -> Result<Value, String> {
    run_engine(
        &app,
        &state,
        "audit_certification",
        json!({"manifest_path": request.manifest_path}),
    )
    .await
}

#[tauri::command]
async fn convert_dataset(
    app: AppHandle,
    state: State<'_, EngineState>,
    request: ConversionRequest,
) -> Result<Value, String> {
    run_engine(
        &app,
        &state,
        "convert",
        json!({
            "input_path": request.input_path,
            "output_path": request.output_path,
            "input_format": request.input_format,
            "output_format": request.output_format,
            "input_options": request.input_options,
            "output_options": request.output_options,
        }),
    )
    .await
}

#[tauri::command]
async fn validate_dataset(
    app: AppHandle,
    state: State<'_, EngineState>,
    request: ValidationRequest,
) -> Result<Value, String> {
    run_engine(
        &app,
        &state,
        "validate",
        json!({
            "input_path": request.input_path,
            "target_format": request.target_format,
            "artifact_directory": request.artifact_directory,
            "input_format": request.input_format,
            "input_options": request.input_options,
            "output_options": request.output_options,
        }),
    )
    .await
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .manage(EngineState::default())
        .invoke_handler(tauri::generate_handler![
            engine_capabilities,
            bridge_diagnostics,
            install_bridge,
            audit_certification,
            convert_dataset,
            validate_dataset
        ])
        .run(tauri::generate_context!())
        .expect("error while running StatData Converter");
}
