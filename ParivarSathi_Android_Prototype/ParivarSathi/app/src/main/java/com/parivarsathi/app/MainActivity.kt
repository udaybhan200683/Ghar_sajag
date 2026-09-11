package com.parivarsathi.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

private val Green = Color(0xFF0B8F3C)
private val DarkGreen = Color(0xFF08752F)
private val LightGreen = Color(0xFFEAF8EE)
private val PaleGreen = Color(0xFFF4FBF6)
private val Red = Color(0xFFD91F26)
private val LightRed = Color(0xFFFFEEEE)
private val Navy = Color(0xFF0D1838)
private val Muted = Color(0xFF60739D)
private val BluePale = Color(0xFFEAF2FF)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { ParivarSathiApp() }
    }
}

enum class Tab { Home, Devices, Reports, Settings }

data class Device(
    val name: String,
    val subtitle: String,
    val icon: ImageVector,
    val active: Boolean,
    val battery: Int,
    val remaining: String,
    val updated: String
)

@Composable
fun ParivarSathiApp() {
    var tab by remember { mutableStateOf(Tab.Home) }
    var away by remember { mutableStateOf(false) }
    var alertDemo by remember { mutableStateOf(false) }

    MaterialTheme(colorScheme = lightColorScheme(primary = Green, background = Color(0xFFFAFCFA))) {
        Scaffold(
            containerColor = Color(0xFFFAFCFA),
            bottomBar = {
                NavigationBar(containerColor = Color.White) {
                    NavItem(Tab.Home, tab, Icons.Default.Home) { tab = Tab.Home }
                    NavItem(Tab.Devices, tab, Icons.Default.Wifi) { tab = Tab.Devices }
                    NavItem(Tab.Reports, tab, Icons.Default.Assessment) { tab = Tab.Reports }
                    NavItem(Tab.Settings, tab, Icons.Default.Settings) { tab = Tab.Settings }
                }
            }
        ) { pad ->
            Column(Modifier.padding(pad).fillMaxSize()) {
                TopHeader(away = away, onAwayChange = { away = it })
                when (tab) {
                    Tab.Home -> HomeScreen(away = away, alertDemo = alertDemo, onToggleScenario = { alertDemo = !alertDemo })
                    Tab.Devices -> DevicesScreen()
                    Tab.Reports -> ReportsScreen()
                    Tab.Settings -> SettingsScreen()
                }
            }
        }
    }
}

@Composable
private fun RowScope.NavItem(tab: Tab, selected: Tab, icon: ImageVector, onClick: () -> Unit) {
    NavigationBarItem(
        selected = tab == selected,
        onClick = onClick,
        icon = { Icon(icon, contentDescription = tab.name) },
        label = { Text(tab.name) },
        colors = NavigationBarItemDefaults.colors(selectedIconColor = Green, selectedTextColor = Green, indicatorColor = LightGreen)
    )
}

@Composable
fun TopHeader(away: Boolean, onAwayChange: (Boolean) -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(Icons.Default.Home, null, tint = Green, modifier = Modifier.size(52.dp))
        Spacer(Modifier.width(8.dp))
        Column(Modifier.weight(1f)) {
            Text("Parivar Sathi", color = Navy, fontSize = 26.sp, fontWeight = FontWeight.Bold)
            Text("Apno ka khayal, har pal", color = Muted, fontSize = 15.sp)
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Switch(checked = away, onCheckedChange = onAwayChange, colors = SwitchDefaults.colors(checkedTrackColor = Green))
            Text("Away", color = Navy, fontSize = 14.sp)
        }
        Spacer(Modifier.width(14.dp))
        Column(horizontalAlignment = Alignment.End) {
            Text("Mon, 16 Sep 2024", fontSize = 12.sp, color = Navy)
            Text("10:24 AM", fontSize = 20.sp, fontWeight = FontWeight.Bold, color = Navy)
        }
    }
}

@Composable
fun HomeScreen(away: Boolean, alertDemo: Boolean, onToggleScenario: () -> Unit) {
    val alert = alertDemo || away
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            StatusHero(alert = alert, away = away)
        }
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                SummaryCard(
                    modifier = Modifier.weight(1f),
                    icon = Icons.Default.Favorite,
                    title = "I am OK",
                    line1 = if (alert) "not confirmed" else "1 hr ago",
                    line2 = if (alert) "today" else "confirmed",
                    negative = alert
                )
                SummaryCard(
                    modifier = Modifier.weight(1f),
                    icon = Icons.Default.MeetingRoom,
                    title = "Main door",
                    line1 = if (alert) "Open" else "Closed",
                    line2 = if (alert) "Open since 2 hrs\nNo indoor activity" else "Indoor activity · 14 min ago",
                    negative = alert
                )
            }
        }
        item {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                SummaryCard(
                    modifier = Modifier.weight(1f),
                    icon = Icons.Default.NightsStay,
                    title = "Night activity",
                    line1 = if (alert) "8 bathroom visits" else "2 bathroom visits,",
                    line2 = if (alert) "unusual" else "no concern",
                    negative = alert
                )
                SummaryCard(
                    modifier = Modifier.weight(1f),
                    icon = Icons.Default.BatteryAlert,
                    title = "Device health",
                    line1 = if (alert) "Bathroom sensor 5%" else "Lowest battery:\nBedroom sensor 42%",
                    line2 = if (alert) "recharge in 2 hrs" else "Recharge in ~5 days",
                    negative = alert
                )
            }
        }
        item {
            RecentEvents(alert)
        }
        item {
            OutlinedButton(onClick = onToggleScenario, modifier = Modifier.fillMaxWidth()) {
                Text(if (alertDemo) "Show normal demo" else "Show alert demo")
            }
        }
    }
}

@Composable
private fun StatusHero(alert: Boolean, away: Boolean) {
    val bg = if (alert) LightRed else LightGreen
    val iconBg = if (alert) Red else Color(0xFF39B54A)
    Card(colors = CardDefaults.cardColors(containerColor = bg), shape = RoundedCornerShape(22.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(72.dp).clip(CircleShape).background(iconBg), contentAlignment = Alignment.Center) {
                    Icon(if (alert) Icons.Default.PriorityHigh else Icons.Default.Check, null, tint = Color.White, modifier = Modifier.size(44.dp))
                }
                Spacer(Modifier.width(14.dp))
                Column {
                    Text(
                        if (away) "Away mode active" else if (alert) "Attention needed at home" else "Home looks normal",
                        color = Navy,
                        fontSize = 27.sp,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        if (away) "Home safety monitoring is active." else if (alert) "Please check the home status." else "All is well at home.",
                        color = if (alert) Red else DarkGreen,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                SmallStatus(Icons.Default.WbSunny, if (alert) "Morning activity\nmissing" else "Morning routine\ncompleted", if (alert) Red else Navy, Modifier.weight(1f))
                SmallStatus(Icons.Default.Shield, if (alert || away) "Unusual\nactivity" else "No unusual\nactivity", if (alert || away) Red else Navy, Modifier.weight(1f))
                SmallStatus(Icons.Default.Wifi, "4/4 devices\nonline", Navy, Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun SmallStatus(icon: ImageVector, text: String, color: Color, modifier: Modifier = Modifier) {
    Row(modifier.background(Color.White.copy(alpha = .75f), RoundedCornerShape(14.dp)).padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = if (color == Red) Red else Green)
        Spacer(Modifier.width(8.dp))
        Text(text, fontSize = 12.sp, color = color)
    }
}

@Composable
private fun SummaryCard(modifier: Modifier, icon: ImageVector, title: String, line1: String, line2: String, negative: Boolean) {
    Card(colors = CardDefaults.cardColors(containerColor = if (negative) LightRed else LightGreen), shape = RoundedCornerShape(20.dp), modifier = modifier) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.Top) {
            Box(Modifier.size(48.dp).clip(CircleShape).background(if (negative) Color(0xFFFFDADA) else Color(0xFFE1F5E7)), contentAlignment = Alignment.Center) {
                Icon(icon, null, tint = if (negative) Red else DarkGreen)
            }
            Spacer(Modifier.width(10.dp))
            Column {
                Text(title, color = Navy, fontWeight = FontWeight.Bold, fontSize = 17.sp)
                Text(line1, color = if (negative) Red else DarkGreen, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                Text(line2, color = if (negative) Red else if (title == "I am OK" || title == "Night activity") DarkGreen else Muted, fontSize = 14.sp)
            }
        }
    }
}

@Composable
private fun RecentEvents(alert: Boolean) {
    val events = if (alert) listOf(
        Triple("10:22 AM", "Main door opened", Red),
        Triple("9:50 AM", "Bathroom visit detected", Red),
        Triple("8:16 AM", "Motion in Drawing Room", Red),
        Triple("6:45 AM", "Bathroom sensor battery 5%", Red),
        Triple("6:30 AM", "Morning activity missed", Red)
    ) else listOf(
        Triple("10:32 AM", "I'm OK received", DarkGreen),
        Triple("10:05 AM", "Motion in Drawing Room", Color(0xFF0B55D9)),
        Triple("9:20 AM", "Main door closed", DarkGreen),
        Triple("9:18 AM", "Main door opened", Red),
        Triple("7:42 AM", "Morning routine completed", DarkGreen)
    )
    Card(colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(20.dp), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Schedule, null, tint = Green)
                Spacer(Modifier.width(8.dp))
                Text("Recent important events", color = Navy, fontWeight = FontWeight.Bold, fontSize = 20.sp, modifier = Modifier.weight(1f))
                Text("View all", color = Color(0xFF1268D8), fontSize = 14.sp)
            }
            Spacer(Modifier.height(8.dp))
            events.forEach { (time, text, color) ->
                Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(time, color = Muted, modifier = Modifier.width(82.dp))
                    Box(Modifier.size(9.dp).clip(CircleShape).background(Color(0xFFAEBBCD)))
                    Spacer(Modifier.width(10.dp))
                    Text(text, color = color, modifier = Modifier.weight(1f))
                }
            }
        }
    }
}

@Composable
fun DevicesScreen() {
    val devices = listOf(
        Device("Hub", "Living Room Hub", Icons.Default.Router, true, 82, "Estimated backup ~18 hrs", "Last updated 10 min ago"),
        Device("Bedroom Node", "Motion Sensor", Icons.Default.DirectionsRun, true, 42, "Estimated time left ~5 days", "Last updated 24 min ago"),
        Device("Drawing Room Node", "Motion Sensor", Icons.Default.DirectionsRun, true, 68, "Estimated time left ~9 days", "Last updated 16 min ago"),
        Device("Main Door Node", "Door Sensor", Icons.Default.MeetingRoom, true, 55, "Estimated time left ~12 days", "Last updated 14 min ago"),
        Device("Bathroom Node", "Motion Sensor", Icons.Default.DirectionsRun, false, 5, "Estimated time left ~2 hrs", "Last seen 2 hrs ago"),
        Device("Pooja Room Node", "Motion Sensor", Icons.Default.DirectionsRun, true, 81, "Estimated time left ~20 days", "Last updated 31 min ago")
    )
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Card(colors = CardDefaults.cardColors(containerColor = LightGreen), shape = RoundedCornerShape(20.dp)) {
                Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(70.dp).clip(CircleShape).background(Color(0xFF42B94D)), contentAlignment = Alignment.Center) {
                        Icon(Icons.Default.Router, null, tint = Color.White, modifier = Modifier.size(40.dp))
                    }
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        Text("6 devices total", color = Navy, fontSize = 24.sp, fontWeight = FontWeight.Bold)
                        Text("Keeping your home connected and safe.", color = Muted)
                    }
                    StatusCount("5", "active", false)
                    Spacer(Modifier.width(8.dp))
                    StatusCount("1", "inactive", true)
                }
            }
        }
        items(devices) { DeviceCard(it) }
    }
}

@Composable
private fun StatusCount(num: String, label: String, bad: Boolean) {
    Column(Modifier.background(if (bad) LightRed else Color(0xFFDDF7E5), RoundedCornerShape(14.dp)).padding(horizontal = 16.dp, vertical = 10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(num, color = Navy, fontSize = 22.sp, fontWeight = FontWeight.Bold)
        Text(label, color = if (bad) Red else DarkGreen)
    }
}

@Composable
private fun DeviceCard(d: Device) {
    var expanded by remember { mutableStateOf(false) }
    val low = d.battery <= 10
    Card(
        colors = CardDefaults.cardColors(containerColor = if (!d.active || low) LightRed else LightGreen),
        shape = RoundedCornerShape(20.dp),
        modifier = Modifier.fillMaxWidth().clickable { expanded = !expanded }
    ) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(58.dp).clip(CircleShape).background(if (low) Color(0xFFFFDADA) else BluePale), contentAlignment = Alignment.Center) {
                    Icon(d.icon, null, tint = if (low) Red else Color(0xFF1268D8), modifier = Modifier.size(34.dp))
                }
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(d.name, color = Navy, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                    Text(d.subtitle, color = Muted)
                    Text(if (d.active) "● Active" else "● Inactive", color = if (d.active) Green else Red, fontWeight = FontWeight.Medium)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        BatteryIcon(d.battery)
                        Spacer(Modifier.width(8.dp))
                        Text("${d.battery}%", color = Navy, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                    }
                    Text(d.remaining, color = if (low) Red else DarkGreen, fontSize = 14.sp)
                    Text(d.updated, color = Muted, fontSize = 12.sp)
                }
            }
            if (expanded) {
                Divider(Modifier.padding(vertical = 10.dp))
                Text("Device details", fontWeight = FontWeight.Bold, color = Navy)
                Text("Signal quality: Good", color = Muted)
                Text("Firmware: v0.1", color = Muted)
            }
        }
    }
}

@Composable
private fun BatteryIcon(level: Int) {
    val c = when { level <= 10 -> Red; level < 60 -> Color(0xFFFFB000); else -> Green }
    Box(Modifier.width(64.dp).height(28.dp)) {
        Box(Modifier.width(56.dp).height(24.dp).clip(RoundedCornerShape(4.dp)).background(Color.White).align(Alignment.CenterStart))
        Box(Modifier.width(56.dp).height(24.dp).clip(RoundedCornerShape(4.dp)).background(Color.Transparent).align(Alignment.CenterStart))
        Box(Modifier.width((56 * level.coerceIn(4,100) / 100f).dp).height(24.dp).clip(RoundedCornerShape(4.dp)).background(c).align(Alignment.CenterStart))
        Box(Modifier.width(4.dp).height(10.dp).background(Color.Gray).align(Alignment.CenterEnd))
    }
}

@Composable
fun ReportsScreen() {
    var period by remember { mutableStateOf(1) }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Card(colors = CardDefaults.cardColors(containerColor = LightGreen), shape = RoundedCornerShape(20.dp)) {
                Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Assessment, null, tint = Green, modifier = Modifier.size(52.dp))
                    Spacer(Modifier.width(12.dp))
                    Column {
                        Text("Reports", color = Navy, fontWeight = FontWeight.Bold, fontSize = 25.sp)
                        Text("Daily and weekly family care summary", color = Muted)
                    }
                }
            }
        }
        item {
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                listOf("Today", "This Week", "This Month").forEachIndexed { idx, text ->
                    SegmentedButton(selected = period == idx, onClick = { period = idx }, shape = SegmentedButtonDefaults.itemShape(idx, 3)) { Text(text) }
                }
            }
        }
        item { ReportGlance() }
        item { ActivityTrend() }
        item { KeyInsights() }
        item {
            Button(onClick = {}, modifier = Modifier.fillMaxWidth(), colors = ButtonDefaults.buttonColors(containerColor = Green)) {
                Icon(Icons.Default.Download, null)
                Spacer(Modifier.width(8.dp))
                Text("Download PDF")
            }
        }
    }
}

@Composable private fun ReportGlance() {
    Card(colors = CardDefaults.cardColors(containerColor = LightGreen), shape = RoundedCornerShape(20.dp)) {
        Column(Modifier.padding(16.dp)) {
            Text("This week at a glance", color = Navy, fontSize = 20.sp, fontWeight = FontWeight.Bold)
            Text("Key highlights from 9 – 15 Sep 2024", color = Muted)
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Metric("Morning routine", "6/7 days", Icons.Default.WbSunny, Modifier.weight(1f))
                Metric("I am OK", "5/7 days", Icons.Default.CheckCircle, Modifier.weight(1f))
                Metric("Night activity", "2 visits", Icons.Default.NightsStay, Modifier.weight(1f))
                Metric("Unusual alerts", "1", Icons.Default.Warning, Modifier.weight(1f), true)
            }
        }
    }
}

@Composable private fun Metric(title: String, value: String, icon: ImageVector, modifier: Modifier, red: Boolean = false) {
    Column(modifier.background(Color.White.copy(alpha=.8f), RoundedCornerShape(14.dp)).padding(10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(icon, null, tint = if (red) Red else Green)
        Text(title, color = Navy, fontSize = 11.sp)
        Text(value, color = if (red) Red else DarkGreen, fontWeight = FontWeight.Bold, fontSize = 17.sp)
    }
}

@Composable private fun ActivityTrend() {
    val vals = listOf(62,78,112,76,48,69,83)
    Card(colors = CardDefaults.cardColors(containerColor = LightGreen), shape = RoundedCornerShape(20.dp)) {
        Column(Modifier.padding(16.dp)) {
            Text("Activity trend", color = Navy, fontWeight = FontWeight.Bold, fontSize = 20.sp)
            Text("Daily activity level (number of sensor events)", color = Muted)
            Spacer(Modifier.height(14.dp))
            Row(Modifier.fillMaxWidth().height(130.dp), verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.SpaceEvenly) {
                vals.forEachIndexed { idx, v ->
                    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Bottom, modifier = Modifier.fillMaxHeight()) {
                        Text(v.toString(), color = Navy, fontSize = 11.sp)
                        Box(Modifier.width(34.dp).height((v/1.2f).dp).background(Color(0xFF45CB78), RoundedCornerShape(topStart=5.dp, topEnd=5.dp)))
                        Text(listOf("M","T","W","T","F","S","S")[idx], color = Muted, fontSize = 11.sp)
                    }
                }
            }
        }
    }
}

@Composable private fun KeyInsights() {
    val insights = listOf(
        "Routine was normal on most days" to "Morning routine completed on 6 out of 7 days.",
        "Higher night activity seen on Wed" to "Night activity was higher than usual on Wednesday.",
        "Main door activity lower than usual on Fri" to "Fewer main door events compared to usual.",
        "One device needed battery attention" to "Bathroom sensor battery low this week."
    )
    Card(colors = CardDefaults.cardColors(containerColor = LightGreen), shape = RoundedCornerShape(20.dp)) {
        Column(Modifier.padding(16.dp)) {
            Text("Key insights", color = Navy, fontWeight = FontWeight.Bold, fontSize = 20.sp)
            insights.forEach { (a,b) ->
                Spacer(Modifier.height(8.dp))
                Text(a, color = Navy, fontWeight = FontWeight.Bold)
                Text(b, color = Muted, fontSize = 13.sp)
            }
        }
    }
}

@Composable
fun SettingsScreen() {
    var dialog by remember { mutableStateOf<String?>(null) }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Text("Settings", color = Navy, fontSize = 28.sp, fontWeight = FontWeight.Bold)
            Text("Customize your home and device preferences", color = Muted)
        }
        item { SettingsGroup("Home Settings", listOf(
            Triple("Home Details", "Update home name, location and preferences", Icons.Default.Home),
            Triple("Family Members", "Manage family access and permissions", Icons.Default.Group),
            Triple("Wi‑Fi & Network", "Manage your home network", Icons.Default.Wifi)
        )) { dialog = it } }
        item { SettingsGroup("Device Settings", listOf(
            Triple("Manage Devices", "View, rename or remove devices", Icons.Default.Settings),
            Triple("Notifications", "Set alerts for critical activities", Icons.Default.Notifications),
            Triple("Battery Alerts", "Set low battery notifications", Icons.Default.BatteryAlert),
            Triple("Device Schedules", "Set active hours and device modes", Icons.Default.Schedule)
        )) { dialog = it } }
        item { SettingsGroup("App Settings", listOf(
            Triple("Privacy & Security", "Manage data and security settings", Icons.Default.Security),
            Triple("Help & Support", "FAQs, user guide and contact support", Icons.Default.Help),
            Triple("About", "App version, terms and policies", Icons.Default.Info)
        )) { dialog = it } }
    }
    dialog?.let { title ->
        AlertDialog(onDismissRequest = { dialog = null }, confirmButton = { TextButton(onClick = { dialog = null }) { Text("OK") } }, title = { Text(title) }, text = { Text("This prototype screen is wired for navigation. Connect this action to your backend/device configuration in the next integration step.") })
    }
}

@Composable
private fun SettingsGroup(title: String, rows: List<Triple<String,String,ImageVector>>, onClick: (String)->Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = Color.White), shape = RoundedCornerShape(18.dp)) {
        Column {
            Text(title, color = Muted, fontWeight = FontWeight.Bold, modifier = Modifier.padding(14.dp))
            rows.forEach { (name, sub, icon) ->
                Row(Modifier.fillMaxWidth().clickable { onClick(name) }.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(44.dp).clip(CircleShape).background(BluePale), contentAlignment = Alignment.Center) { Icon(icon, null, tint = Green) }
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(name, color = Navy, fontWeight = FontWeight.Bold)
                        Text(sub, color = Muted, fontSize = 13.sp)
                    }
                    Icon(Icons.Default.ChevronRight, null, tint = Muted)
                }
                Divider()
            }
        }
    }
}
