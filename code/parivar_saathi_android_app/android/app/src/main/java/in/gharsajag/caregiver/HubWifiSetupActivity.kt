package `in`.gharsajag.caregiver

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothManager
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.ViewGroup
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts

/** GS-58 discovery-only entry point. BLE advertisement names are never proof of Hub identity. */
class HubWifiSetupActivity : ComponentActivity() {
    private val handler = Handler(Looper.getMainLooper())
    private var scanner: android.bluetooth.le.BluetoothLeScanner? = null
    private var scanning = false
    private var status: TextView? = null
    private var devices: TextView? = null
    private var scanButton: Button? = null
    private val names = linkedSetOf<String>()
    private val stopScan = Runnable { stopDiscovery("Discovery finished. Select and secure a Hub only after approved pairing is available.") }

    private val permissionRequest = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { grants ->
        if (grants.isNotEmpty() && grants.values.all { it }) startDiscovery()
        else showStatus("Nearby device permission denied. No Hub settings were changed.")
    }

    private val callback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            val name = result.scanRecord?.deviceName ?: return
            // This Espressif convention narrows discovery only. It is spoofable.
            if (HubWifiDiscoveryPolicy.isCandidateName(name)) runOnUiThread {
                if (scanning && names.size < 20 && names.add(name)) {
                    devices?.text = names.joinToString("\n") { "$it · identity unverified" }
                }
            }
        }

        override fun onScanFailed(errorCode: Int) {
            runOnUiThread {
                stopDiscovery("BLE discovery failed. Retry when Bluetooth is available; no settings were changed.")
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val column = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(32, 40, 32, 32)
        }
        fun label(text: String): TextView = TextView(this).also {
            it.text = text
            it.textSize = 17f
            it.setPadding(0, 0, 0, 24)
            column.addView(it)
        }
        label("Add Hub · Wi-Fi setup").textSize = 23f
        label("Find nearby setup radios. A name or QR reference does not verify the Hub or authorize Wi-Fi changes.")
        status = label("Setup is incomplete until device-specific pairing, protected credential storage and Home claim are available.")
        scanButton = Button(this).also {
            it.text = "Find nearby Hubs"
            it.setOnClickListener { requestDiscovery() }
            column.addView(it)
        }
        devices = label("No nearby Hub observed.")
        label("Wi-Fi network selection and password entry are locked until authorized pairing and encrypted device storage are enabled. No password is requested or saved here.")
        val cancel = Button(this).also {
            it.text = "Cancel"
            it.setOnClickListener { finish() }
            column.addView(it)
        }
        val scroll = ScrollView(this).apply { addView(column) }
        setContentView(scroll, ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
    }

    private fun requiredPermissions(): Array<String> = if (Build.VERSION.SDK_INT >= 31)
        arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
    else arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)

    private fun requestDiscovery() {
        val missing = requiredPermissions().filter {
            checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) permissionRequest.launch(missing.toTypedArray())
        else startDiscovery()
    }

    @SuppressLint("MissingPermission")
    private fun startDiscovery() {
        if (scanning || isFinishing || isDestroyed) return
        val adapter = (getSystemService(BLUETOOTH_SERVICE) as? BluetoothManager)?.adapter
        try {
            if (adapter == null || !adapter.isEnabled) {
                showStatus("Bluetooth is off or unavailable. Enable it and retry.")
                return
            }
            val selected = adapter.bluetoothLeScanner
            if (selected == null) {
                showStatus("BLE discovery is unavailable on this phone.")
                return
            }
            names.clear()
            devices?.text = "Searching for nearby setup radios…"
            selected.startScan(null,
                ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_POWER).build(), callback)
            scanner = selected
            scanning = true
            scanButton?.isEnabled = false
            showStatus("Scanning for up to 10 seconds. Discovered names are unverified.")
            handler.postDelayed(stopScan, 10_000L)
        } catch (_: SecurityException) {
            stopDiscovery("Nearby device permission is unavailable. No Hub settings were changed.")
        } catch (_: IllegalStateException) {
            stopDiscovery("BLE discovery could not start. No Hub settings were changed.")
        }
    }

    @SuppressLint("MissingPermission")
    private fun stopDiscovery(message: String) {
        handler.removeCallbacks(stopScan)
        val active = scanner
        scanner = null
        if (scanning && active != null) {
            try { active.stopScan(callback) } catch (_: SecurityException) { /* permission revoked */ }
        }
        scanning = false
        scanButton?.isEnabled = true
        if (names.isEmpty()) devices?.text = "No nearby Hub setup radio observed."
        showStatus(message)
    }

    private fun showStatus(message: String) { status?.text = message }

    override fun onStop() {
        stopDiscovery("Discovery stopped when the app left the screen. No Hub settings were changed.")
        super.onStop()
    }
}

/** An advertisement is only an untrusted discovery hint. */
object HubWifiDiscoveryPolicy {
    fun isCandidateName(name: String): Boolean =
        name.length in 7..32 && name.startsWith("PROV_") &&
            name.drop(5).all { it in 'A'..'Z' || it in 'a'..'z' || it in '0'..'9' || it == '_' }
}
