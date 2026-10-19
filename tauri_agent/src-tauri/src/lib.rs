use enigo::{Enigo, Key, KeyboardControllable, MouseButton, MouseControllable};
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::{Read, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{Arc, Mutex, OnceLock};
use std::thread;

fn mouse_button(button: i32) -> Option<MouseButton> {
    match button {
        0 => Some(MouseButton::Left),
        1 => Some(MouseButton::Middle),
        2 => Some(MouseButton::Right),
        _ => None,
    }
}

fn keyboard_key(key: &str) -> Option<Key> {
    match key {
        "Alt" => Some(Key::Alt),
        "Backspace" => Some(Key::Backspace),
        "CapsLock" => Some(Key::CapsLock),
        "Control" => Some(Key::Control),
        "Delete" => Some(Key::Delete),
        "ArrowDown" => Some(Key::DownArrow),
        "End" => Some(Key::End),
        "Enter" => Some(Key::Return),
        "Escape" => Some(Key::Escape),
        "F1" => Some(Key::F1),
        "F2" => Some(Key::F2),
        "F3" => Some(Key::F3),
        "F4" => Some(Key::F4),
        "F5" => Some(Key::F5),
        "F6" => Some(Key::F6),
        "F7" => Some(Key::F7),
        "F8" => Some(Key::F8),
        "F9" => Some(Key::F9),
        "F10" => Some(Key::F10),
        "F11" => Some(Key::F11),
        "F12" => Some(Key::F12),
        "Home" => Some(Key::Home),
        "ArrowLeft" => Some(Key::LeftArrow),
        "Meta" => Some(Key::Meta),
        "PageDown" => Some(Key::PageDown),
        "PageUp" => Some(Key::PageUp),
        "ArrowRight" => Some(Key::RightArrow),
        "Shift" => Some(Key::LShift),
        " " => Some(Key::Space),
        "Tab" => Some(Key::Tab),
        "ArrowUp" => Some(Key::UpArrow),
        value if value.chars().count() == 1 => {
            value.chars().next().map(|character| Key::Layout(character.to_ascii_lowercase()))
        }
        _ => None,
    }
}

static ENIGO: OnceLock<Mutex<Enigo>> = OnceLock::new();

fn get_enigo() -> &'static Mutex<Enigo> {
    ENIGO.get_or_init(|| Mutex::new(Enigo::new()))
}

#[tauri::command]
fn move_mouse(x: f64, y: f64) {
    if let Ok(mut enigo) = get_enigo().lock() {
        let (width, height) = enigo.main_display_size();
        let target_x = (x.clamp(0.0, 1.0) * f64::from(width.saturating_sub(1))).round() as i32;
        let target_y = (y.clamp(0.0, 1.0) * f64::from(height.saturating_sub(1))).round() as i32;
        enigo.mouse_move_to(target_x, target_y);
    }
}

#[tauri::command]
fn mouse_event(button: i32, is_down: bool) {
    if let Some(button) = mouse_button(button) {
        if let Ok(mut enigo) = get_enigo().lock() {
            if is_down {
                enigo.mouse_down(button);
            } else {
                enigo.mouse_up(button);
            }
        }
    }
}

#[tauri::command]
fn scroll_mouse(delta_x: i32, delta_y: i32) {
    if let Ok(mut enigo) = get_enigo().lock() {
        if delta_x != 0 {
            enigo.mouse_scroll_x(delta_x.clamp(-20, 20));
        }
        if delta_y != 0 {
            enigo.mouse_scroll_y(delta_y.clamp(-20, 20));
        }
    }
}

#[tauri::command]
fn key_event(key: String, is_down: bool) {
    if let Some(key) = keyboard_key(&key) {
        if let Ok(mut enigo) = get_enigo().lock() {
            if is_down {
                enigo.key_down(key);
            } else {
                enigo.key_up(key);
            }
        }
    }
}

// ═════════════════════════════════════════════════════════════
// Native Terminal Execution
// ═════════════════════════════════════════════════════════════

struct TerminalSession {
    _child: Child,
    stdin: ChildStdin,
    output_buffer: Arc<Mutex<Vec<u8>>>,
}

static TERMINAL: OnceLock<Mutex<Option<TerminalSession>>> = OnceLock::new();

fn get_terminal_state() -> &'static Mutex<Option<TerminalSession>> {
    TERMINAL.get_or_init(|| Mutex::new(None))
}

#[tauri::command]
fn start_terminal() -> Result<String, String> {
    let mut state = get_terminal_state().lock().map_err(|e| e.to_string())?;
    if state.is_some() {
        return Ok("Terminal already running".to_string());
    }

    #[cfg(target_os = "windows")]
    let mut cmd = Command::new("cmd.exe");

    #[cfg(not(target_os = "windows"))]
    let mut cmd = {
        let shell = std::env::var("SHELL").unwrap_or_else(|_| "/bin/sh".to_string());
        let mut c = Command::new(shell);
        c.arg("-i");
        c
    };

    cmd.stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mut child = cmd.spawn().map_err(|e| format!("Failed to spawn shell: {}", e))?;
    let stdin = child.stdin.take().ok_or_else(|| "Failed to capture stdin".to_string())?;
    let stdout = child.stdout.take().ok_or_else(|| "Failed to capture stdout".to_string())?;
    let stderr = child.stderr.take().ok_or_else(|| "Failed to capture stderr".to_string())?;

    let output_buffer = Arc::new(Mutex::new(Vec::new()));

    // Stdout reader thread
    let buf_out = Arc::clone(&output_buffer);
    thread::spawn(move || {
        let mut reader = stdout;
        let mut chunk = [0u8; 1024];
        loop {
            match reader.read(&mut chunk) {
                Ok(0) => break,
                Ok(n) => {
                    if let Ok(mut buf) = buf_out.lock() {
                        buf.extend_from_slice(&chunk[..n]);
                    }
                }
                Err(_) => break,
            }
        }
    });

    // Stderr reader thread
    let buf_err = Arc::clone(&output_buffer);
    thread::spawn(move || {
        let mut reader = stderr;
        let mut chunk = [0u8; 1024];
        loop {
            match reader.read(&mut chunk) {
                Ok(0) => break,
                Ok(n) => {
                    if let Ok(mut buf) = buf_err.lock() {
                        buf.extend_from_slice(&chunk[..n]);
                    }
                }
                Err(_) => break,
            }
        }
    });

    *state = Some(TerminalSession {
        _child: child,
        stdin,
        output_buffer,
    });

    Ok("Terminal started".to_string())
}

#[tauri::command]
fn write_terminal(data: String) -> Result<(), String> {
    let mut state = get_terminal_state().lock().map_err(|e| e.to_string())?;
    if let Some(session) = state.as_mut() {
        let normalized = data.replace('\r', "\n");
        session.stdin
            .write_all(normalized.as_bytes())
            .map_err(|e| format!("Write failed: {}", e))?;
        session.stdin.flush().map_err(|e| format!("Flush failed: {}", e))?;
        Ok(())
    } else {
        Err("Terminal not running".to_string())
    }
}

#[tauri::command]
fn read_terminal() -> Result<String, String> {
    let state = get_terminal_state().lock().map_err(|e| e.to_string())?;
    if let Some(session) = state.as_ref() {
        let mut buf = session.output_buffer.lock().map_err(|e| e.to_string())?;
        if buf.is_empty() {
            Ok(String::new())
        } else {
            let drained: Vec<u8> = buf.drain(..).collect();
            Ok(String::from_utf8_lossy(&drained).to_string())
        }
    } else {
        Ok(String::new())
    }
}

#[tauri::command]
fn close_terminal() -> Result<(), String> {
    let mut state = get_terminal_state().lock().map_err(|e| e.to_string())?;
    if let Some(mut session) = state.take() {
        let _ = session._child.kill();
    }
    Ok(())
}

// ═════════════════════════════════════════════════════════════
// Native Filesystem Helpers
// ═════════════════════════════════════════════════════════════

#[derive(Serialize, Deserialize)]
pub struct FileEntry {
    name: String,
    path: String,
    is_dir: bool,
    size: u64,
}

#[tauri::command]
fn fs_get_home() -> String {
    std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .unwrap_or_else(|_| ".".to_string())
}

#[tauri::command]
fn fs_list_dir(dir_path: String) -> Result<Vec<FileEntry>, String> {
    let path = PathBuf::from(&dir_path);
    if !path.exists() || !path.is_dir() {
        return Err(format!("Directory not found: {}", dir_path));
    }

    let entries = fs::read_dir(&path).map_err(|e| e.to_string())?;
    let mut results = Vec::new();

    for entry in entries.flatten() {
        let p = entry.path();
        let name = entry.file_name().to_string_lossy().to_string();
        let is_dir = p.is_dir();
        let size = if is_dir { 0 } else { entry.metadata().map(|m| m.len()).unwrap_or(0) };

        results.push(FileEntry {
            name,
            path: p.to_string_lossy().to_string(),
            is_dir,
            size,
        });
    }

    results.sort_by(|a, b| match (a.is_dir, b.is_dir) {
        (true, false) => std::cmp::Ordering::Less,
        (false, true) => std::cmp::Ordering::Greater,
        _ => a.name.to_lowercase().cmp(&b.name.to_lowercase()),
    });

    Ok(results)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            move_mouse,
            mouse_event,
            scroll_mouse,
            key_event,
            start_terminal,
            write_terminal,
            read_terminal,
            close_terminal,
            fs_get_home,
            fs_list_dir
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
