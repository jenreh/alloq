// Custom macOS menu and About panel. Kept out of main.rs: reflex-desktop rewrites the
// region between the notification bridge and `fn port_available` on every build.
#[cfg(target_os = "macos")]
pub mod about {
    use objc2::rc::Retained;
    use objc2::runtime::AnyObject;
    use objc2::{AnyThread, MainThreadMarker};
    use objc2_app_kit::{
        NSAboutPanelOptionApplicationIcon, NSAboutPanelOptionApplicationVersion,
        NSAboutPanelOptionCredits, NSApplication, NSColor, NSImage, NSFont, NSFontAttributeName, NSForegroundColorAttributeName,
        NSLinkAttributeName, NSMutableParagraphStyle, NSParagraphStyleAttributeName,
        NSTextAlignment,
    };
    use objc2_foundation::{
        ns_string, NSData, NSDictionary, NSMutableAttributedString, NSRange,
        NSString, NSURL,
    };

    const COPYRIGHT: &str = "\u{a9} 2026 Jens Rehp\u{f6}hler";
    const PREFIX: &str = "Ressourcenplanung f\u{fc}r Softwareteams";
    const REPO_LABEL: &str = "github.com/jenreh/alloq";
    const REPO_URL: &str = "https://github.com/jenreh/alloq";
    const LICENSE: &str = "MIT-Lizenz";
    const ICON: &[u8] = include_bytes!("../icons/128x128@2x.png");

    fn credits() -> Retained<NSMutableAttributedString> {
        let text = format!("{PREFIX}\n{REPO_LABEL} \u{b7} {LICENSE}");
        let credits = NSMutableAttributedString::from_nsstring(&NSString::from_str(&text));
        let whole = NSRange::new(0, text.encode_utf16().count());
        let link_start = PREFIX.encode_utf16().count() + 1;
        let link = NSRange::new(link_start, REPO_LABEL.encode_utf16().count());
        unsafe {
            let style = NSMutableParagraphStyle::new();
            style.setAlignment(NSTextAlignment::Center);
            let font = NSFont::systemFontOfSize(11.0);
            let color = NSColor::labelColor();
            credits.addAttribute_value_range(NSFontAttributeName, &font, whole);
            credits.addAttribute_value_range(NSForegroundColorAttributeName, &color, whole);
            credits.addAttribute_value_range(NSParagraphStyleAttributeName, &style, whole);
            if let Some(url) = NSURL::URLWithString(&NSString::from_str(REPO_URL)) {
                credits.addAttribute_value_range(NSLinkAttributeName, &url, link);
            }
        }
        credits
    }

    pub fn show(version: &str) {
        let Some(mtm) = MainThreadMarker::new() else {
            return;
        };
        let version = NSString::from_str(version);
        let copyright = NSString::from_str(COPYRIGHT);
        let credits = credits();
        let icon = NSImage::initWithData(NSImage::alloc(), &NSData::with_bytes(ICON));
        unsafe {
            let mut keys: Vec<&NSString> = vec![
                NSAboutPanelOptionApplicationVersion,
                ns_string!("Copyright"),
                NSAboutPanelOptionCredits,
            ];
            let mut values: Vec<&AnyObject> = vec![&version, &copyright, &credits];
            if let Some(icon) = icon.as_deref() {
                keys.push(NSAboutPanelOptionApplicationIcon);
                values.push(icon);
            }
            let options = NSDictionary::from_slices(&keys, &values);
            NSApplication::sharedApplication(mtm).orderFrontStandardAboutPanelWithOptions(&options);
        }
    }
}

// Default macOS menu, but "About" opens our own panel (version, copyright, link).
pub fn build_menu(app: &tauri::AppHandle) -> tauri::Result<tauri::menu::Menu<tauri::Wry>> {
    use tauri::menu::{Menu, MenuItem, PredefinedMenuItem, Submenu};

    let menu = Menu::default(app)?;
    #[cfg(target_os = "macos")]
    {
        let name = app.package_info().name.clone();
        let product = app.config().product_name.clone().unwrap_or(name);
        let about = MenuItem::with_id(
            app,
            "about",
            format!("\u{dc}ber {product}"),
            true,
            None::<&str>,
        )?;
        let app_menu = Submenu::with_items(
            app,
            &product,
            true,
            &[
                &about,
                &PredefinedMenuItem::separator(app)?,
                &PredefinedMenuItem::services(app, None)?,
                &PredefinedMenuItem::separator(app)?,
                &PredefinedMenuItem::hide(app, None)?,
                &PredefinedMenuItem::hide_others(app, None)?,
                &PredefinedMenuItem::show_all(app, None)?,
                &PredefinedMenuItem::separator(app)?,
                &PredefinedMenuItem::quit(app, None)?,
            ],
        )?;
        menu.remove(&menu.items()?[0])?;
        menu.insert(&app_menu, 0)?;
    }
    #[cfg(not(target_os = "macos"))]
    let _ = (MenuItem::<tauri::Wry>::with_id, PredefinedMenuItem::<tauri::Wry>::separator, Submenu::<tauri::Wry>::new);
    Ok(menu)
}
