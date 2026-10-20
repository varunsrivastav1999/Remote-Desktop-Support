use enigo::{Enigo, Key, KeyboardControllable, MouseButton, MouseControllable};
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::{Read, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::{mpsc, Arc, Mutex, OnceLock};
use tauri::Manager;
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};
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

enum InputCommand {
    Move(f64, f64),
    Button(MouseButton, bool),
    Scroll(i32, i32),
    Key(Key, bool),
}

// enigo's macOS handle is not Send, so a single thread owns it and replays commands in order
static INPUT: OnceLock<Mutex<mpsc::Sender<InputCommand>>> = OnceLock::new();

fn send_input(command: InputCommand) {
    let sender = INPUT.get_or_init(|| {
        let (sender, receiver) = mpsc::channel::<InputCommand>();
        thread::spawn(move || {
            let mut enigo = Enigo::new();
            for command in receiver {
                match command {
                    InputCommand::Move(x, y) => {
                        let (width, height) = enigo.main_display_size();
                        let target_x = (x.clamp(0.0, 1.0) * f64::from(width.saturating_sub(1))).round() as i32;
                        let target_y = (y.clamp(0.0, 1.0) * f64::from(height.saturating_sub(1))).round() as i32;
                        enigo.mouse_move_to(target_x, target_y);
                    }
                    InputCommand::Button(button, true) => enigo.mouse_down(button),
                    InputCommand::Button(button, false) => enigo.mouse_up(button),
                    InputCommand::Scroll(delta_x, delta_y) => {
                        if delta_x != 0 {
                            enigo.mouse_scroll_x(delta_x.clamp(-20, 20));
                        }
                        if delta_y != 0 {
                            enigo.mouse_scroll_y(delta_y.clamp(-20, 20));
                        }
                    }
                    InputCommand::Key(key, true) => enigo.key_down(key),
                    InputCommand::Key(key, false) => enigo.key_up(key),
                }
            }
        });
        Mutex::new(sender)
    });
    if let Ok(sender) = sender.lock() {
        let _ = sender.send(command);
    }
}

#[tauri::command]
fn move_mouse(x: f64, y: f64) {
    send_input(InputCommand::Move(x, y));
}

#[tauri::command]
fn mouse_event(button: i32, is_down: bool) {
    if let Some(button) = mouse_button(button) {
        send_input(InputCommand::Button(button, is_down));
    }
}

#[tauri::command]
fn scroll_mouse(delta_x: i32, delta_y: i32) {
    send_input(InputCommand::Scroll(delta_x, delta_y));
}

#[tauri::command]
fn key_event(key: String, is_down: bool) {
    if let Some(key) = keyboard_key(&key) {
        send_input(InputCommand::Key(key, is_down));
    }
}

// ═════════════════════════════════════════════════════════════
// Input Permission (macOS Accessibility) and Start at Login
// ═════════════════════════════════════════════════════════════

#[cfg(target_os = "macos")]
mod accessibility {
    use core_foundation::base::TCFType;
    use core_foundation::boolean::CFBoolean;
    use core_foundation::dictionary::{CFDictionary, CFDictionaryRef};
    use core_foundation::string::CFString;

    #[link(name = "ApplicationServices", kind = "framework")]
    extern "C" {
        fn AXIsProcessTrusted() -> bool;
        fn AXIsProcessTrustedWithOptions(options: CFDictionaryRef) -> bool;
    }

    /// Without Accessibility, macOS silently drops injected mouse and keyboard events.
    pub fn is_trusted(prompt: bool) -> bool {
        if !prompt {
            return unsafe { AXIsProcessTrusted() };
        }
        let options = CFDictionary::from_CFType_pairs(&[(
            CFString::new("AXTrustedCheckOptionPrompt"),
            CFBoolean::true_value(),
        )]);
        unsafe { AXIsProcessTrustedWithOptions(options.as_concrete_TypeRef()) }
    }
}

/// Whether this app may inject input; `None` where no permission is needed.
#[tauri::command]
fn input_permission(prompt: bool) -> Option<bool> {
    #[cfg(target_os = "macos")]
    {
        Some(accessibility::is_trusted(prompt))
    }
    #[cfg(not(target_os = "macos"))]
    {
        let _ = prompt;
        None
    }
}

#[tauri::command]
fn get_autostart(app: tauri::AppHandle) -> Result<bool, String> {
    app.autolaunch().is_enabled().map_err(|e| e.to_string())
}

#[tauri::command]
fn set_autostart(app: tauri::AppHandle, enabled: bool) -> Result<bool, String> {
    let launcher = app.autolaunch();
    if enabled {
        launcher.enable().map_err(|e| e.to_string())?;
    } else {
        launcher.disable().map_err(|e| e.to_string())?;
    }
    launcher.is_enabled().map_err(|e| e.to_string())
}

/// Start at login is on by default, once: turning it off later (here or in the OS) sticks.
fn enable_autostart_on_first_run(app: &tauri::AppHandle) {
    let Ok(dir) = app.path().app_config_dir() else { return };
    let marker = dir.join("autostart-initialized");
    if marker.exists() {
        return;
    }
    if app.autolaunch().enable().is_ok() {
        let _ = fs::create_dir_all(&dir);
        let _ = fs::write(&marker, b"1");
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

const BASE64_ALPHABET: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

fn base64_encode(data: &[u8]) -> String {
    let mut result = String::with_capacity((data.len() + 2) / 3 * 4);
    for chunk in data.chunks(3) {
        let b0 = chunk[0];
        let b1 = if chunk.len() > 1 { chunk[1] } else { 0 };
        let b2 = if chunk.len() > 2 { chunk[2] } else { 0 };

        result.push(BASE64_ALPHABET[(b0 >> 2) as usize] as char);
        result.push(BASE64_ALPHABET[(((b0 & 0x03) << 4) | (b1 >> 4)) as usize] as char);
        if chunk.len() > 1 {
            result.push(BASE64_ALPHABET[(((b1 & 0x0f) << 2) | (b2 >> 6)) as usize] as char);
        } else {
            result.push('=');
        }
        if chunk.len() > 2 {
            result.push(BASE64_ALPHABET[(b2 & 0x3f) as usize] as char);
        } else {
            result.push('=');
        }
    }
    result
}

fn base64_decode(input: &str) -> Option<Vec<u8>> {
    let clean: Vec<u8> = input.bytes().filter(|b| !b.is_ascii_whitespace()).collect();
    if clean.len() % 4 != 0 {
        return None;
    }
    let mut result = Vec::with_capacity(clean.len() / 4 * 3);
    let decode_char = |c: u8| -> Option<u8> {
        match c {
            b'A'..=b'Z' => Some(c - b'A'),
            b'a'..=b'z' => Some(c - b'a' + 26),
            b'0'..=b'9' => Some(c - b'0' + 52),
            b'+' => Some(62),
            b'/' => Some(63),
            _ => None,
        }
    };
    for chunk in clean.chunks(4) {
        let c0 = decode_char(chunk[0])?;
        let c1 = decode_char(chunk[1])?;
        result.push((c0 << 2) | (c1 >> 4));
        if chunk[2] != b'=' {
            let c2 = decode_char(chunk[2])?;
            result.push(((c1 & 0x0f) << 4) | (c2 >> 2));
            if chunk[3] != b'=' {
                let c3 = decode_char(chunk[3])?;
                result.push(((c2 & 0x03) << 6) | c3);
            }
        }
    }
    Some(result)
}

#[derive(Serialize, Deserialize)]
pub struct ReadChunkResult {
    data: String,
    size: usize,
    total_size: u64,
    eof: bool,
    name: String,
}

#[tauri::command]
fn fs_read_chunk(file_path: String, offset: u64, size: usize) -> Result<ReadChunkResult, String> {
    use std::io::Seek;
    let path = PathBuf::from(&file_path);
    if !path.exists() {
        return Err("File not found".to_string());
    }
    let mut file = fs::File::open(&path).map_err(|e| e.to_string())?;
    let total_size = file.metadata().map(|m| m.len()).unwrap_or(0);
    file.seek(std::io::SeekFrom::Start(offset)).map_err(|e| e.to_string())?;
    let mut buf = vec![0u8; size];
    let bytes_read = file.read(&mut buf).map_err(|e| e.to_string())?;
    buf.truncate(bytes_read);
    let eof = offset + (bytes_read as u64) >= total_size || bytes_read == 0;
    let name = path.file_name().unwrap_or_default().to_string_lossy().to_string();
    Ok(ReadChunkResult {
        data: base64_encode(&buf),
        size: bytes_read,
        total_size,
        eof,
        name,
    })
}

#[tauri::command]
fn fs_write_chunk(dest_dir: String, filename: String, chunk_b64: String, offset: u64) -> Result<(), String> {
    use std::io::Seek;
    let dir = PathBuf::from(&dest_dir);
    if !dir.exists() {
        fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    }
    let target = dir.join(&filename);
    let data = base64_decode(&chunk_b64).ok_or_else(|| "Invalid base64 payload".to_string())?;
    let mut file = if offset == 0 {
        fs::File::create(&target).map_err(|e| e.to_string())?
    } else {
        fs::OpenOptions::new().write(true).open(&target).map_err(|e| e.to_string())?
    };
    file.seek(std::io::SeekFrom::Start(offset)).map_err(|e| e.to_string())?;
    file.write_all(&data).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
fn fs_delete(target_path: String) -> Result<(), String> {
    let p = PathBuf::from(&target_path);
    if !p.exists() {
        return Ok(());
    }
    if p.is_dir() {
        fs::remove_dir_all(&p).map_err(|e| e.to_string())
    } else {
        fs::remove_file(&p).map_err(|e| e.to_string())
    }
}

#[tauri::command]
fn fs_mkdir(target_path: String) -> Result<(), String> {
    let p = PathBuf::from(&target_path);
    fs::create_dir_all(&p).map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            Some(vec!["--autostarted"]),
        ))
        .setup(|app| {
            enable_autostart_on_first_run(app.handle());
            Ok(())
        })
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
            fs_list_dir,
            fs_read_chunk,
            fs_write_chunk,
            fs_delete,
            fs_mkdir,
            input_permission,
            get_autostart,
            set_autostart
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
