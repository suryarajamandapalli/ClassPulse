// js/dashboard.js

// Dynamic backend URL configuration
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? ''
    : 'https://classpulse-backend.onrender.com'; // Replace with your public backend URL (e.g. Render/Railway)

// Global state
let students = [];
let chart = null;
let activeStudentId = null;

// Audio context for scanning beeps
let audioCtx = null;

// Webcam scanner state
let mediaStream = null;
let scanningActive = false;
let jsqrTimer = null;
let quaggaFrameTimer = null;

// Initialize dashboard on DOM load
document.addEventListener('DOMContentLoaded', function() {
    // Check authentication
    if (localStorage.getItem('isLoggedIn') !== 'true') {
        window.location.href = 'index.html';
        return;
    }

    // Set welcome message
    document.getElementById('welcomeUser').textContent = localStorage.getItem('username') || 'Admin';

    // Initialize UI components
    setupEventListeners();
    fetchStudents();
});

// Fetch all students from backend
async function fetchStudents() {
    try {
        const response = await fetch(API_BASE + '/api/students');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (data.status === 'ok') {
            students = data.students;
            refreshUI();
        } else {
            showToast('Failed to fetch students from database', 'error');
        }
    } catch (error) {
        console.error('Error fetching students:', error);
        showToast('Error connecting to backend server', 'error');
    }
}

// Refresh entire UI (Table, Stats, Chart, Active Profile)
function refreshUI() {
    filterStudents();
    updateStats();
    initializeChart();
    if (activeStudentId) {
        showStudentProfile(activeStudentId); // refresh active profile drawer
    }
}

// Render student table
function renderStudentTable(filteredStudents) {
    const tbody = document.getElementById('studentTableBody');
    tbody.innerHTML = '';

    if (filteredStudents.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="px-6 py-10 text-center text-sm text-slate-500 bg-slate-900/10">
                    <i class="fas fa-search mb-2 text-slate-600 text-lg"></i>
                    <p>No matching student records found</p>
                </td>
            </tr>
        `;
        return;
    }

    filteredStudents.forEach(student => {
        const row = document.createElement('tr');
        row.className = 'hover:bg-slate-900/30 border-b border-slate-900/40 cursor-pointer transition duration-150';
        
        // Calculate attendance percentage
        const total = student.total_classes || 40;
        const attended = student.classes_attended || 0;
        const percentage = Math.round((attended / total) * 100);

        const attendanceColor = percentage >= 85 ? 'text-emerald-400' : 
                               percentage >= 75 ? 'text-amber-400' : 'text-rose-500';
        
        const progressBarColor = percentage >= 85 ? 'bg-emerald-500' : 
                                  percentage >= 75 ? 'bg-amber-500' : 'bg-rose-500';

        const statusBadge = student.presentToday ? 
            '<span class="px-2.5 py-1 text-xs font-semibold bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-full flex items-center w-fit"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse"></span>Present</span>' :
            '<span class="px-2.5 py-1 text-xs font-semibold bg-slate-950/60 border border-slate-800 text-slate-400 rounded-full flex items-center w-fit"><span class="w-1.5 h-1.5 rounded-full bg-slate-500 mr-1.5"></span>Absent</span>';

        row.innerHTML = `
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex items-center">
                    <img class="h-10 w-10 rounded-xl object-cover border border-slate-800" src="${student.photo || 'https://picsum.photos/seed/' + student.student_id + '/200/200'}" alt="${student.name}" onerror="this.src='https://picsum.photos/seed/default/200/200'">
                    <div class="ml-4">
                        <div class="text-sm font-semibold text-slate-200">${student.name}</div>
                        <div class="text-xs text-slate-400">${student.email || ''}</div>
                    </div>
                </div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="text-sm font-mono text-slate-300 font-semibold">${student.roll_no || student.student_id}</div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">
                <span class="px-2.5 py-1 text-xs font-semibold bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-lg">${student.branch}</span>
            </td>
            <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-300 font-semibold">${student.section || 'A'}</td>
            <td class="px-6 py-4 whitespace-nowrap">
                <div class="flex items-center justify-between text-xs font-semibold mb-1">
                    <span class="${attendanceColor}">${percentage}%</span>
                    <span class="text-slate-400 font-normal">${attended}/${total} classes</span>
                </div>
                <div class="w-28 bg-slate-950 rounded-full h-1.5 border border-slate-900">
                    <div class="${progressBarColor} h-1.5 rounded-full" style="width: ${percentage}%"></div>
                </div>
            </td>
            <td class="px-6 py-4 whitespace-nowrap">${statusBadge}</td>
            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium">
                <button onclick="openStudentProfile('${student.student_id}')" class="bg-indigo-900/30 hover:bg-indigo-900/60 border border-indigo-800/50 hover:border-indigo-700/60 text-indigo-300 px-3 py-1.5 rounded-xl transition duration-200">
                    <i class="fas fa-id-card mr-1 text-xs"></i>View
                </button>
            </td>
        `;
        
        row.addEventListener('click', (e) => {
            // Only open if click was not on action button
            if (!e.target.closest('button')) {
                openStudentProfile(student.student_id);
            }
        });
        tbody.appendChild(row);
    });
}

// Update statistics counters
function updateStats() {
    const total = students.length;
    if (total === 0) return;

    const present = students.filter(s => s.presentToday).length;
    const absent = total - present;

    // Average overall percentage
    let totalPercentageSum = 0;
    students.forEach(s => {
        const p = Math.round(((s.classes_attended || 0) / (s.total_classes || 40)) * 100);
        totalPercentageSum += p;
    });
    const avg = Math.round(totalPercentageSum / total);

    document.getElementById('totalStudents').textContent = total;
    document.getElementById('presentToday').textContent = present;
    document.getElementById('absentToday').textContent = absent;
    document.getElementById('avgAttendance').textContent = avg + '%';
}

// Initialize and render analytics Chart
function initializeChart() {
    const canvas = document.getElementById('attendanceChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    // Group student percentages by branch
    const branchStats = {};
    students.forEach(s => {
        const b = s.branch || 'CSE';
        const p = Math.round(((s.classes_attended || 0) / (s.total_classes || 40)) * 100);
        if (!branchStats[b]) {
            branchStats[b] = [];
        }
        branchStats[b].push(p);
    });

    const labels = Object.keys(branchStats).sort();
    const branchAverages = labels.map(b => {
        const list = branchStats[b];
        return Math.round(list.reduce((sum, val) => sum + val, 0) / list.length);
    });

    if (chart) {
        chart.destroy();
    }

    // Chart.js gradient fill
    const gradient = ctx.createLinearGradient(0, 0, 0, 340);
    gradient.addColorStop(0, 'rgba(99, 102, 241, 0.85)');
    gradient.addColorStop(1, 'rgba(99, 102, 241, 0.05)');

    chart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Average Attendance Rate (%)',
                data: branchAverages,
                backgroundColor: gradient,
                borderColor: '#6366f1',
                borderWidth: 2,
                borderRadius: 8,
                barThickness: 32,
                shadowColor: 'rgba(99, 102, 241, 0.3)',
                shadowBlur: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.04)'
                    },
                    ticks: {
                        color: '#94a3b8',
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#94a3b8'
                    }
                }
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#0f172a',
                    titleColor: '#e2e8f0',
                    bodyColor: '#e2e8f0',
                    borderColor: 'rgba(255, 255, 255, 0.08)',
                    borderWidth: 1,
                    callbacks: {
                        label: function(context) {
                            return ` Average: ${context.parsed.y}%`;
                        }
                    }
                }
            }
        }
    });
}

// Setup event listeners
function setupEventListeners() {
    // Filters
    document.getElementById('searchInput').addEventListener('input', filterStudents);
    document.getElementById('branchFilter').addEventListener('change', filterStudents);
    document.getElementById('sectionFilter').addEventListener('change', filterStudents);
    
    // Scanner triggers
    document.getElementById('scanBtn').addEventListener('click', () => {
        initAudio();
        openWebcamScanner();
    });
    document.getElementById('closeScannerBtn').addEventListener('click', closeWebcamScanner);
    
    // Drawer profile triggers
    document.getElementById('closePanelBtn').addEventListener('click', closeStudentProfile);

    // Test image triggers
    document.getElementById('openTestImageBtn').addEventListener('click', openTestImageModal);
    document.getElementById('closeFileTestBtn').addEventListener('click', closeTestImageModal);
    document.getElementById('decodeMarkBtn').addEventListener('click', handleFileDecode);
}

// Filter students locally in memory based on search inputs
function filterStudents() {
    const searchTerm = document.getElementById('searchInput').value.trim().toLowerCase();
    const branchFilter = document.getElementById('branchFilter').value;
    const sectionFilter = document.getElementById('sectionFilter').value;
    
    const filtered = students.filter(student => {
        const searchString = `${student.name} ${student.roll_no || student.student_id} ${student.branch}`.toLowerCase();
        const matchesSearch = searchString.includes(searchTerm);
        
        const matchesBranch = !branchFilter || student.branch === branchFilter;
        const matchesSection = !sectionFilter || (student.section || 'A') === sectionFilter;
        
        return matchesSearch && matchesBranch && matchesSection;
    });
    
    renderStudentTable(filtered);
}

// Open profile side panel
function openStudentProfile(studentId) {
    activeStudentId = studentId;
    const student = students.find(s => s.student_id === studentId);
    if (!student) return;

    const total = student.total_classes || 40;
    const attended = student.classes_attended || 0;
    const percentage = Math.round((attended / total) * 100);

    const attendanceColor = percentage >= 85 ? 'text-emerald-400' : 
                           percentage >= 75 ? 'text-amber-400' : 'text-rose-400';

    // AI analytics report generator
    const generateAIReport = (s, p) => {
        const modules = ['Engineering Maths', 'Data Structures', 'Operating Systems', 'Database Systems'];
        let irregular = [];
        if (p < 75) {
            irregular.push(modules[1]);
        }
        if (p < 60) {
            irregular.push(modules[3]);
        }
        const verdict = p >= 85 ? 'consistent and outstanding engagement' : 
                       (p >= 75 ? 'satisfactory, meeting standards' : 'irregular and requires close academic monitoring');
        const extra = irregular.length ? `. Attendance dips noticed in: ${irregular.join(', ')}` : '';
        return `Student shows ${verdict}${extra}. Recommendation: Maintain present streak of 6 sessions to push score to optimal standards.`;
    };

    const profileHTML = `
        <div class="text-center mb-6">
            <div class="relative w-28 h-28 mx-auto mb-3">
                <img src="${student.photo || 'https://picsum.photos/seed/' + student.student_id + '/200/200'}" alt="${student.name}" class="w-full h-full rounded-2xl object-cover border-2 border-slate-800" onerror="this.src='https://picsum.photos/seed/default/200/200'">
                <div class="absolute -bottom-1 -right-1 w-5 h-5 rounded-full border-2 border-slate-950 ${student.presentToday ? 'bg-emerald-500' : 'bg-slate-600'}"></div>
            </div>
            <h3 class="text-xl font-bold text-slate-100">${student.name}</h3>
            <p class="text-sm font-semibold font-mono text-slate-400 mt-0.5">${student.roll_no || student.student_id}</p>
        </div>
        
        <div class="space-y-4">
            <!-- Academic Information -->
            <div class="bg-slate-900/60 border border-slate-905 p-4 rounded-xl">
                <h4 class="font-bold text-slate-200 mb-2.5 text-xs uppercase tracking-wider"><i class="fas fa-graduation-cap mr-1.5 text-indigo-400"></i>Academic Info</h4>
                <div class="space-y-2 text-sm">
                    <div class="flex justify-between">
                        <span class="text-slate-400">Branch:</span>
                        <span class="font-semibold text-slate-200">${student.branch}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-400">Section:</span>
                        <span class="font-semibold text-slate-200">Section ${student.section || 'A'}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-400">Total Attendance:</span>
                        <span class="font-bold ${attendanceColor}">${percentage}% (${attended}/${total})</span>
                    </div>
                </div>
            </div>
            
            <!-- AI Insights -->
            <div class="bg-indigo-950/20 border border-indigo-900/40 p-4 rounded-xl">
                <h4 class="font-bold text-indigo-300 mb-2 text-xs uppercase tracking-wider"><i class="fas fa-brain mr-1.5 text-indigo-400"></i>AI Insights</h4>
                <p class="text-xs text-indigo-200/80 leading-relaxed">${generateAIReport(student, percentage)}</p>
            </div>

            <!-- Contact Information -->
            <div class="bg-slate-900/60 border border-slate-905 p-4 rounded-xl">
                <h4 class="font-bold text-slate-200 mb-2.5 text-xs uppercase tracking-wider"><i class="fas fa-address-book mr-1.5 text-indigo-400"></i>Contact Info</h4>
                <div class="space-y-2 text-xs">
                    <div class="flex justify-between">
                        <span class="text-slate-400">Email:</span>
                        <span class="font-semibold text-indigo-400 select-all">${student.email || 'N/A'}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-400">Phone:</span>
                        <span class="font-semibold text-slate-200 select-all">${student.phone || 'N/A'}</span>
                    </div>
                    <div class="flex justify-between">
                        <span class="text-slate-400">Address:</span>
                        <span class="font-semibold text-slate-200 text-right ml-2">${student.address || 'N/A'}</span>
                    </div>
                </div>
            </div>
            
            <!-- Today's Status -->
            <div class="bg-slate-900/60 border border-slate-905 p-4 rounded-xl text-center">
                <h4 class="font-bold text-slate-200 mb-2.5 text-xs uppercase tracking-wider"><i class="fas fa-clock mr-1.5 text-indigo-400"></i>Attendance Today</h4>
                <div class="flex justify-center mb-3">
                    ${student.presentToday ? 
                        '<span class="inline-flex items-center px-4 py-1.5 rounded-xl text-sm font-semibold bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"><i class="fas fa-check mr-2"></i>Present</span>' :
                        '<span class="inline-flex items-center px-4 py-1.5 rounded-xl text-sm font-semibold bg-slate-950 border border-slate-800 text-slate-400"><i class="fas fa-times mr-2"></i>Absent</span>'
                    }
                </div>
                <!-- Toggle Button -->
                <button onclick="toggleAttendance('${student.student_id}')" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white py-2.5 rounded-xl transition duration-200 font-semibold active:scale-[0.98]">
                    ${student.presentToday ? 'Mark as Absent' : 'Mark as Present'}
                </button>
            </div>
        </div>
    `;

    document.getElementById('studentProfile').innerHTML = profileHTML;
    document.getElementById('sidePanel').classList.add('open');
}

// Close student profile side panel
function closeStudentProfile() {
    activeStudentId = null;
    document.getElementById('sidePanel').classList.remove('open');
}

// Toggle attendance for a student
async function toggleAttendance(studentId) {
    try {
        const response = await fetch(API_BASE + '/api/attendance/toggle', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ student_id: studentId, class_id: 1 })
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (data.status === 'ok') {
            // Update student in our local list
            const student = students.find(s => s.student_id === studentId);
            if (student) {
                student.presentToday = data.presentToday;
                student.classes_attended = data.classes_attended;
                
                // Audio beep feedback
                if (data.presentToday) {
                    playBeepSuccess();
                } else {
                    playBeepError();
                }

                // Show Toast Notification
                showToast(
                    `${student.name} marked as ${data.presentToday ? 'Present' : 'Absent'}`,
                    data.presentToday ? 'success' : 'info'
                );
                
                // Refresh views
                refreshUI();
            }
        }
    } catch (error) {
        console.error('Error toggling attendance:', error);
        showToast('Failed to toggle attendance status on database', 'error');
    }
}

// Webcam scanning implementation
async function openWebcamScanner() {
    document.getElementById('scannerOverlay').style.display = 'flex';
    document.getElementById('scanStatus').textContent = 'Requesting camera stream...';
    
    try {
        stopWebcamScanner(); // clean up if running
        mediaStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment' },
            audio: false
        });
        
        // Remove existing video elements in scanner container (avoid duplicates)
        const vids = document.getElementById('scanner').querySelectorAll('video');
        vids.forEach(v => {
            try { v.pause(); v.srcObject = null; } catch(e) {}
            v.remove();
        });
        
        const video = document.createElement('video');
        video.id = 'scannerVideo';
        video.setAttribute('playsinline', '');
        video.style.width = '100%';
        video.style.height = '100%';
        video.style.objectFit = 'cover';
        
        const canvas = document.getElementById('qrCanvas');
        const scanner = document.getElementById('scanner');
        scanner.insertBefore(video, canvas);
        
        video.srcObject = mediaStream;
        await video.play();
        
        document.getElementById('scanStatus').textContent = 'Camera live — Align code in frame...';
        startWebcamDecoding(video, canvas);
    } catch (err) {
        console.error('Camera stream access denied or failed:', err);
        document.getElementById('scanStatus').textContent = 'Camera error: ' + (err.name || err.message);
        showToast('Failed to access camera. Use Test Image for file uploading instead.', 'error');
    }
}

function closeWebcamScanner() {
    stopWebcamScanner();
    document.getElementById('scannerOverlay').style.display = 'none';
}

function stopWebcamScanner() {
    scanningActive = false;
    if (jsqrTimer) { clearTimeout(jsqrTimer); jsqrTimer = null; }
    if (quaggaFrameTimer) { clearTimeout(quaggaFrameTimer); quaggaFrameTimer = null; }
    if (mediaStream) {
        try {
            mediaStream.getTracks().forEach(track => track.stop());
        } catch (e) {}
        mediaStream = null;
    }
    
    // Cleanup video elements
    const vids = document.getElementById('scanner').querySelectorAll('video');
    vids.forEach(v => {
        try { v.pause(); v.srcObject = null; } catch(e) {}
        v.remove();
    });
}

function startWebcamDecoding(video, canvas) {
    scanningActive = true;
    const ctx = canvas.getContext('2d');
    
    // 1) BarcodeDetector Native API
    if ('BarcodeDetector' in window) {
        try {
            const detector = new BarcodeDetector({
                formats: ['qr_code', 'code_128', 'ean_13', 'ean_8', 'code_39', 'upc_e', 'upc_a']
            });
            const detectLoop = async () => {
                if (!scanningActive) return;
                try {
                    const detections = await detector.detect(video);
                    if (detections && detections.length > 0) {
                        handleScannedBarcode(detections[0].rawValue);
                        return;
                    }
                } catch (e) {
                    console.warn('BarcodeDetector error:', e);
                }
                jsqrTimer = setTimeout(detectLoop, 150);
            };
            detectLoop();
            return; // Use native if supported
        } catch (e) {
            console.warn('BarcodeDetector init failed:', e);
        }
    }
    
    // 2) Fallback to jsQR for QR codes
    const jsQRLoop = () => {
        if (!scanningActive) return;
        if (video.readyState === video.HAVE_ENOUGH_DATA) {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
            try {
                const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                const code = jsQR(imgData.data, imgData.width, imgData.height);
                if (code && code.data) {
                    handleScannedBarcode(code.data);
                    return;
                }
            } catch (err) {
                console.warn('jsQR scan error:', err);
            }
        }
        jsqrTimer = setTimeout(jsQRLoop, 180);
    };
    jsQRLoop();
    
    // 3) Fallback to Quagga (decodes frame-by-frame) for 1D Barcodes
    const quaggaLoop = () => {
        if (!scanningActive) return;
        if (video.readyState === video.HAVE_ENOUGH_DATA) {
            try {
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
                
                Quagga.decodeSingle({
                    src: dataUrl,
                    numOfWorkers: 0,
                    inputStream: { size: 800 },
                    decoder: {
                        readers: ['code_128_reader', 'code_39_reader', 'ean_reader', 'ean_8_reader', 'upc_reader']
                    }
                }, function(result) {
                    if (result && result.codeResult && result.codeResult.code) {
                        handleScannedBarcode(result.codeResult.code);
                        return;
                    }
                });
            } catch (err) {
                console.warn('Quagga scan error:', err);
            }
        }
        quaggaFrameTimer = setTimeout(quaggaLoop, 750);
    };
    quaggaLoop();
}

// Send scanned barcode to API
async function handleScannedBarcode(code) {
    if (!scanningActive) return;
    scanningActive = false; // stop loops
    
    try {
        const response = await fetch(API_BASE + '/api/attendance/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ barcode: code, class_id: 1 })
        });
        
        const data = await response.json();
        if (response.ok && data.status === 'ok') {
            playBeepSuccess();
            showToast(`${data.name}: ${data.message}`, 'success');
            
            // Reload student list
            await fetchStudents();
            
            // If scanner was open, close it
            setTimeout(() => {
                closeWebcamScanner();
                if (data.student_id) {
                    openStudentProfile(data.student_id);
                }
            }, 800);
        } else {
            playBeepError();
            showToast(data.message || 'Invalid barcode scan', 'error');
            // Resume scanning after 2 seconds
            setTimeout(() => {
                scanningActive = true;
                const video = document.getElementById('scannerVideo');
                const canvas = document.getElementById('qrCanvas');
                if (video && canvas) {
                    startWebcamDecoding(video, canvas);
                }
            }, 2000);
        }
    } catch (err) {
        console.error('Error submitting scan:', err);
        playBeepError();
        showToast('Server connection failed', 'error');
        closeWebcamScanner();
    }
}

// Test Image File Modal Actions
function openTestImageModal() {
    document.getElementById('fileTestModal').classList.remove('hidden');
    document.getElementById('decodeResult').textContent = '';
    document.getElementById('decodeResult').className = 'mt-4 text-sm font-medium text-slate-300';
    document.getElementById('fileToTestInput').value = '';
}

function closeTestImageModal() {
    document.getElementById('fileTestModal').classList.add('hidden');
}

async function handleFileDecode() {
    const fileInput = document.getElementById('fileToTestInput');
    const file = fileInput.files[0];
    if (!file) {
        alert('Please choose an image file containing a barcode or QR code');
        return;
    }

    const resDiv = document.getElementById('decodeResult');
    resDiv.textContent = 'Analyzing and decoding image...';
    resDiv.className = 'mt-4 text-sm font-medium text-indigo-400';

    const url = URL.createObjectURL(file);
    
    // First try Quagga for 1D Barcode
    Quagga.decodeSingle({
        src: url,
        numOfWorkers: 0,
        inputStream: { size: 1200 },
        decoder: {
            readers: ['code_128_reader', 'code_39_reader', 'ean_reader', 'ean_8_reader', 'upc_reader']
        }
    }, function(result) {
        if (result && result.codeResult && result.codeResult.code) {
            handleUploadedCode(result.codeResult.code, url);
            return;
        }

        // Fallback: try jsQR for QR codes
        const img = new Image();
        img.onload = function() {
            const canvas = document.createElement('canvas');
            canvas.width = img.naturalWidth;
            canvas.height = img.naturalHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0);
            
            try {
                const imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                const qr = jsQR(imgData.data, imgData.width, imgData.height);
                if (qr && qr.data) {
                    handleUploadedCode(qr.data, url);
                } else {
                    resDiv.textContent = 'No decodable barcode or QR code detected. Try a clearer image.';
                    resDiv.className = 'mt-4 text-sm font-semibold text-rose-500';
                    playBeepError();
                    URL.revokeObjectURL(url);
                }
            } catch (e) {
                resDiv.textContent = 'Decoding failed: ' + e.message;
                resDiv.className = 'mt-4 text-sm font-semibold text-rose-500';
                playBeepError();
                URL.revokeObjectURL(url);
            }
        };
        img.onerror = function() {
            resDiv.textContent = 'Failed to load image file';
            resDiv.className = 'mt-4 text-sm font-semibold text-rose-500';
            playBeepError();
            URL.revokeObjectURL(url);
        };
        img.src = url;
    });
}

// Mark attendance from uploaded file code
async function handleUploadedCode(code, objectUrl) {
    const resDiv = document.getElementById('decodeResult');
    resDiv.textContent = `Decoded: ${code}. Submitting to database...`;
    
    try {
        const response = await fetch(API_BASE + '/api/attendance/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ barcode: code, class_id: 1 })
        });
        const data = await response.json();
        
        if (response.ok && data.status === 'ok') {
            playBeepSuccess();
            resDiv.textContent = `Success! Marked present for: ${data.name}`;
            resDiv.className = 'mt-4 text-sm font-semibold text-emerald-400';
            showToast(`Scanned from image: Marked ${data.name} present`, 'success');
            
            await fetchStudents();
            
            setTimeout(() => {
                closeTestImageModal();
                if (data.student_id) {
                    openStudentProfile(data.student_id);
                }
            }, 1000);
        } else {
            playBeepError();
            resDiv.textContent = `API Error: ${data.message || 'No matching student record'}`;
            resDiv.className = 'mt-4 text-sm font-semibold text-rose-500';
            showToast(data.message || 'No student with this barcode', 'error');
        }
    } catch (e) {
        playBeepError();
        resDiv.textContent = 'Server connection failed';
        resDiv.className = 'mt-4 text-sm font-semibold text-rose-500';
    } finally {
        if (objectUrl) {
            URL.revokeObjectURL(objectUrl);
        }
    }
}

// Web Audio API Beeps
function initAudio() {
    if (!audioCtx) {
        try {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        } catch (e) {
            console.warn('Web Audio API not supported on this browser');
        }
    }
    if (audioCtx && audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
}

function playBeepSuccess() {
    initAudio();
    if (!audioCtx) return;
    try {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        
        osc.type = 'sine';
        osc.frequency.setValueAtTime(880, audioCtx.currentTime); // A5 note
        gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
        
        osc.start();
        // Beep frequency change
        setTimeout(() => {
            osc.frequency.setValueAtTime(1320, audioCtx.currentTime); // E6 note
            gain.gain.setValueAtTime(0.04, audioCtx.currentTime);
        }, 80);
        
        osc.stop(audioCtx.currentTime + 0.22);
    } catch (e) {
        console.warn('Error playing success beep:', e);
    }
}

function playBeepError() {
    initAudio();
    if (!audioCtx) return;
    try {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(220, audioCtx.currentTime); // A3 note
        gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
        
        osc.start();
        osc.stop(audioCtx.currentTime + 0.18);
    } catch (e) {
        console.warn('Error playing error beep:', e);
    }
}

// Show animated toast notification
function showToast(message, type = 'info') {
    const holder = document.getElementById('toastHolder');
    if (!holder) return;

    const toast = document.createElement('div');
    toast.className = 'px-4 py-3 rounded-xl shadow-2xl text-slate-100 flex items-center space-x-2 border text-sm pointer-events-auto transform translate-x-full transition-transform duration-300 ease-out min-w-[240px]';
    
    let bg, border, icon;
    if (type === 'success') {
        bg = 'bg-slate-900/95';
        border = 'border-emerald-500/30';
        icon = '<i class="fas fa-check-circle text-emerald-400 text-base"></i>';
    } else if (type === 'error') {
        bg = 'bg-slate-900/95';
        border = 'border-rose-500/30';
        icon = '<i class="fas fa-exclamation-circle text-rose-400 text-base"></i>';
    } else {
        bg = 'bg-slate-900/95';
        border = 'border-sky-500/30';
        icon = '<i class="fas fa-info-circle text-sky-400 text-base"></i>';
    }

    toast.classList.add(bg);
    toast.classList.add(border);
    toast.innerHTML = `
        ${icon}
        <span class="font-medium">${message}</span>
    `;

    holder.appendChild(toast);
    
    // Trigger slide-in
    setTimeout(() => {
        toast.classList.remove('translate-x-full');
    }, 50);

    // Remove toast after 3 seconds
    setTimeout(() => {
        toast.classList.add('translate-x-full');
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 3200);
}

// Logout Admin user
function logout() {
    if (confirm('Are you sure you want to sign out?')) {
        localStorage.removeItem('isLoggedIn');
        localStorage.removeItem('username');
        window.location.href = 'index.html';
    }
}

// Initialize audio context on first user click
document.body.addEventListener('click', () => {
    initAudio();
}, { once: true });

// Prevent camera stream leaking on unload
window.addEventListener('beforeunload', () => {
    stopWebcamScanner();
});
