using System.Windows;

namespace AINovelStudio.DesktopHost.WebView2TestHarness;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        new MainWindow(e.Args).Show();
    }
}
