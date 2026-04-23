import { useState, useEffect, useMemo, useRef } from 'react';
import './App.css';

const TENSION_LEVELS = {
  "OR": "CU1 Prop, OR",
  "MIXTA": "CU12 Prop, Mixta",
  "CLIENTE": "CU1 Prop, Cliente",
  "N2": "CU2",
  "N3": "CU3",
}

function App() {
  const [activeTab, setActiveTab] = useState('upload'); // 'upload', 'resumen', 'config'
  const [uploadSubTab, setUploadSubTab] = useState('operador_red'); // 'operador_red' , 'enerpro'

  // Estados del escáner PDF
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState([]);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  // Estados del escáner CSV
  const [csvFile, setCsvFile] = useState(null);
  const [csvLoading, setCsvLoading] = useState(false);
  const [csvError, setCsvError] = useState(null);
  const [csvSuccess, setCsvSuccess] = useState(null);
  const [csvDragActive, setCsvDragActive] = useState(false);
  const [csvWarning, setCsvWarning] = useState(false);

  const [operador, setOperador] = useState("Afinia");
  const [mes, setMes] = useState(new Date().getMonth() + 1);
  const [anio, setAnio] = useState(new Date().getFullYear());
  
  const [anioOperador, setAnioOperador] = useState(new Date().getFullYear());
  const [anioGlobal, setAnioGlobal] = useState(new Date().getFullYear());
  const [planOperador, setPlanOperador] = useState("Afinia");

  // Estados del formulario Plan enerPro - Parámetros Operador
  const [fijabitHogar, setFijabitHogar] = useState("");
  const [fijabitComercial, setFijabitComercial] = useState("");

  // Estados del formulario Plan enerPro - Cargos Globales
  const [medidaDirectaHogar, setMedidaDirectaHogar] = useState("");
  const [medidaDirectaZc, setMedidaDirectaZc] = useState("");
  const [medidaSemiIndirectaZc, setMedidaSemiIndirectaZc] = useState("");
  const [medidaDirectaComercial, setMedidaDirectaComercial] = useState("");
  const [medidaSemiIndirectaComercial, setMedidaSemiIndirectaComercial] = useState("");

  const [saveSuccessOp, setSaveSuccessOp] = useState(null);
  const [saveSuccessGlobal, setSaveSuccessGlobal] = useState(null);

  const operadoresSoportados = ["Afinia", "enerBit"];
  const meses = [
    { num: 1, name: "Enero" }, { num: 2, name: "Febrero" }, { num: 3, name: "Marzo" },
    { num: 4, name: "Abril" }, { num: 5, name: "Mayo" }, { num: 6, name: "Junio" },
    { num: 7, name: "Julio" }, { num: 8, name: "Agosto" }, { num: 9, name: "Septiembre" },
    { num: 10, name: "Octubre" }, { num: 11, name: "Noviembre" }, { num: 12, name: "Diciembre" }
  ];

  const [warningMessage, setWarningMessage] = useState(null);
  const [awaitingConfirmation, setAwaitingConfirmation] = useState(false);
  const [successMessage, setSuccessMessage] = useState(null);
  
  // Estados para filtros en la tabla
  const [filterMes, setFilterMes] = useState("");
  const [filterAnio, setFilterAnio] = useState(new Date().getFullYear().toString());
  const [filterFuente, setFilterFuente] = useState("todas"); // 'todas', 'afinia', 'enerbit'

  // Datos enerBit
  const [dataEnerbit, setDataEnerbit] = useState([]);

  // Estados del Dashboard Resumen
  const [dashOR, setDashOR] = useState("Afinia");
  const [dashAnio, setDashAnio] = useState(new Date().getFullYear());
  const [dashMes, setDashMes] = useState(new Date().getMonth() + 1);
  const [dashData, setDashData] = useState([]);
  const [dashFijabit, setDashFijabit] = useState(null);
  const [dashFijabitCom, setDashFijabitCom] = useState(null);

  // Estados para Simulación de Ahorro
  const [simConsumo, setSimConsumo] = useState("");
  const [simNivel, setSimNivel] = useState("CU1 Prop, OR");
  const [simEstrato, setSimEstrato] = useState("4");
  const [simMercado, setSimMercado] = useState("Hogar");
  const [simFactor, setSimFactor] = useState("1");
  const [simEsZC, setSimEsZC] = useState("No");

  // Estados extractor de factura
  const [invoiceLoading, setInvoiceLoading] = useState(false);
  const [invoiceResult, setInvoiceResult] = useState(null);
  const [invoiceError, setInvoiceError] = useState(null);
  const invoiceInputRef = useRef(null);

  const handleInvoiceExtract = async (e) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;
    setInvoiceLoading(true);
    setInvoiceResult(null);
    setInvoiceError(null);
    const formData = new FormData();
    formData.append('file', selectedFile);
    try {
      const res = await fetch('http://localhost:8000/invoice-extractor', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw new Error(`HTTP error ${res.status}`);
      const json = await res.json();
      setInvoiceResult(json);
      setSimConsumo(json.consumo_mes_anterior_kwh || "");
      setSimNivel(TENSION_LEVELS[json.propiedad_activo?.toUpperCase()] || "")
      setSimMercado(json.tipo_cliente === "residencial" ? "Hogar" : "Comercial");
      setSimEstrato(json.estrato_clasificacion || "");
    } catch (err) {
      setInvoiceError(err.message);
    } finally {
      setInvoiceLoading(false);
      e.target.value = '';
    }
  };

  const fetchRegistros = () => {
    fetch('http://localhost:8000/registros/')
      .then(res => res.json())
      .then(json => {
        if(Array.isArray(json)) setData(json);
      })
      .catch(err => console.error("Error al cargar historial:", err));
  };

  const fetchRegistrosEnerbit = () => {
    fetch('http://localhost:8000/registros-enerbit/')
      .then(res => res.json())
      .then(json => {
        if(Array.isArray(json)) setDataEnerbit(json);
      })
      .catch(err => console.error("Error al cargar enerBit:", err));
  };

  useEffect(() => {
    fetchRegistros();
    fetchRegistrosEnerbit();
  }, []);

  // Auto-fetch del Dashboard Resumen cuando cambia OR o año
  useEffect(() => {
    if (dashAnio && dashOR) {
      fetch(`http://localhost:8000/dashboard/resumen?anio=${dashAnio}&operador_red=${dashOR}`)
        .then(res => res.json())
        .then(json => {
          setDashData(json.data || []);
          setDashFijabit(json.fijabit_hogar);
          setDashFijabitCom(json.fijabit_comercial);
        })
        .catch(err => console.error("Error al cargar resumen:", err));
    }
  }, [dashAnio, dashOR]);

  // Auto-fetch de Parámetros de Operador cuando cambie el año o el operador
  useEffect(() => {
    fetch(`http://localhost:8000/plan-enerpro/parametros?anio=${anioOperador}&operador_red=${planOperador}`)
      .then(res => res.json())
      .then(json => {
        if (json && json.fijabit_hogar !== undefined) {
          setFijabitHogar(json.fijabit_hogar ?? "");
          setFijabitComercial(json.fijabit_comercial ?? "");
        } else {
          setFijabitHogar("");
          setFijabitComercial("");
        }
      })
      .catch(() => { setFijabitHogar(""); setFijabitComercial(""); });
  }, [anioOperador, planOperador]);

  // Auto-fetch de Cargos Globales cuando cambie el año
  useEffect(() => {
    fetch(`http://localhost:8000/plan-enerpro/globales?anio=${anioGlobal}`)
      .then(res => res.json())
      .then(json => {
        if (json && json.anio !== undefined) {
          setMedidaDirectaHogar(json.medida_directa_hogar ?? "");
          setMedidaDirectaZc(json.medida_directa_zc ?? "");
          setMedidaSemiIndirectaZc(json.medida_semi_indirecta_zc ?? "");
          setMedidaDirectaComercial(json.medida_directa_comercial ?? "");
          setMedidaSemiIndirectaComercial(json.medida_semi_indirecta_comercial ?? "");
        } else {
          setMedidaDirectaHogar(""); setMedidaDirectaZc(""); setMedidaSemiIndirectaZc("");
          setMedidaDirectaComercial(""); setMedidaSemiIndirectaComercial("");
        }
      })
      .catch(() => {
        setMedidaDirectaHogar(""); setMedidaDirectaZc(""); setMedidaSemiIndirectaZc("");
        setMedidaDirectaComercial(""); setMedidaSemiIndirectaComercial("");
      });
  }, [anioGlobal]);

  // Función para guardar Parámetros de Operador
  const handleSaveParametros = () => {
    fetch('http://localhost:8000/plan-enerpro/parametros', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        operador_red: planOperador,
        anio: parseInt(anioOperador),
        fijabit_hogar: fijabitHogar !== "" ? parseFloat(fijabitHogar) : null,
        fijabit_comercial: fijabitComercial !== "" ? parseFloat(fijabitComercial) : null
      })
    })
    .then(res => res.json())
    .then(() => { setSaveSuccessOp("✓ Parámetros guardados"); setTimeout(() => setSaveSuccessOp(null), 3000); })
    .catch(() => { setSaveSuccessOp("✗ Error al guardar"); setTimeout(() => setSaveSuccessOp(null), 3000); });
  };

  // Función para guardar Cargos Globales
  const handleSaveGlobales = () => {
    fetch('http://localhost:8000/plan-enerpro/globales', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        anio: parseInt(anioGlobal),
        medida_directa_hogar: medidaDirectaHogar !== "" ? parseFloat(medidaDirectaHogar) : null,
        medida_directa_zc: medidaDirectaZc !== "" ? parseFloat(medidaDirectaZc) : null,
        medida_semi_indirecta_zc: medidaSemiIndirectaZc !== "" ? parseFloat(medidaSemiIndirectaZc) : null,
        medida_directa_comercial: medidaDirectaComercial !== "" ? parseFloat(medidaDirectaComercial) : null,
        medida_semi_indirecta_comercial: medidaSemiIndirectaComercial !== "" ? parseFloat(medidaSemiIndirectaComercial) : null
      })
    })
    .then(res => res.json())
    .then(() => { setSaveSuccessGlobal("✓ Medidas guardadas"); setTimeout(() => setSaveSuccessGlobal(null), 3000); })
    .catch(() => { setSaveSuccessGlobal("✗ Error al guardar"); setTimeout(() => setSaveSuccessGlobal(null), 3000); });
  };

  // LÓGICA DE AGRUPACIÓN (combina Afinia PDF + enerBit CSV)
  const groupedData = useMemo(() => {
    const groups = {};

    // Incluir datos Afinia (PDF) si el filtro lo permite
    if (filterFuente === 'todas' || filterFuente === 'afinia') {
      data.forEach(row => {
        const groupKey = `afinia-${row.operador_red}-${row.anio}-${row.mes}`;
        if (!groups[groupKey]) {
          groups[groupKey] = {
            operador_red: row.operador_red,
            fuente: 'Afinia (OR)',
            mes: row.mes,
            anio: row.anio,
            registros: []
          };
        }
        groups[groupKey].registros.push(row);
      });
    }

    // Incluir datos enerBit (CSV)
    if (filterFuente === 'todas' || filterFuente === 'enerbit') {
      dataEnerbit.forEach(row => {
        const groupKey = `enerbit-${row.or_asociado}-${row.anio}-${row.mes}`;
        if (!groups[groupKey]) {
          groups[groupKey] = {
            operador_red: 'enerBit',
            fuente: `enerBit → ${row.or_asociado}`,
            mes: row.mes,
            anio: row.anio,
            registros: []
          };
        }
        groups[groupKey].registros.push(row);
      });
    }
    
    return Object.values(groups).sort((a, b) => {
      if (b.anio !== a.anio) return b.anio - a.anio;
      return b.mes - a.mes;
    });
  }, [data, dataEnerbit, filterFuente]);

  const handleDrag = function(e) {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = function(e) {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = function(e) {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file || !operador || !mes || !anio) return;
    setLoading(true);
    setError(null);
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('operador_red', operador);
    formData.append('mes', mes);
    formData.append('anio', anio);
    formData.append('overwrite', awaitingConfirmation ? 'true' : 'false');

    try {
      const response = await fetch('http://localhost:8000/upload-pdf/', {
        method: 'POST',
        body: formData,
      });

      if (response.status === 409) {
          // El archivo existe, pedimos permiso al usuario
          setAwaitingConfirmation(true);
          setLoading(false);
          return;
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      
      if (result.sobreescrito) {
          setSuccessMessage(`Datos sobrescritos y actualizados correctamente.`);
      } else {
          setSuccessMessage(`Datos insertados correctamente en el sistema.`);
      }
      setTimeout(() => setSuccessMessage(null), 5000); // Se borra a los 5s
      
      setAwaitingConfirmation(false);
      setWarningMessage(null);
      // Siempre recargamos los registros frescos de DB
      fetchRegistros();
      setFile(null);  
    } catch (err) {
      setError(err.message);
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  // --- HANDLER CSV (enerBit → guarda en tablas DocumentoEnerbit) ---
  const handleCsvUpload = async (forceOverwrite = false) => {
    if (!csvFile || !operador || !mes || !anio) return;
    setCsvLoading(true);
    setCsvError(null);

    const formData = new FormData();
    formData.append('file', csvFile);
    formData.append('operador_red', operador);
    formData.append('mes', mes);
    formData.append('anio', anio);
    formData.append('overwrite', forceOverwrite ? 'true' : 'false');

    try {
      const response = await fetch('http://localhost:8000/upload-csv/', {
        method: 'POST',
        body: formData,
      });

      if (response.status === 409) {
        setCsvWarning(true);
        setCsvLoading(false);
        return;
      }
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || `HTTP error ${response.status}`);
      }

      const result = await response.json();
      setCsvSuccess(result.sobreescrito
        ? `✓ Datos enerBit sobrescritos: ${result.data.length} registros.`
        : `✓ CSV enerBit guardado: ${result.data.length} registros insertados.`);
      setTimeout(() => setCsvSuccess(null), 5000);
      setCsvWarning(false);
      fetchRegistrosEnerbit();
      setCsvFile(null);
    } catch (err) {
      setCsvError(err.message);
    } finally {
      setCsvLoading(false);
    }
  };

  const renderContent = () => {
    if (activeTab === 'upload') {
      return (
        <div className="tab-content fade-in">
          
          <div className="module-title">
            <h2>Ingesta de Tarifas</h2>
            <p className="text-subtitle">Motor de análisis y digitalización de documentos tarifarios expedidos por los Operadores de Red y configuración de planes.</p>
          </div>

          <div className="segmented-control">
            <button 
              className={`segmented-btn ${uploadSubTab === 'operador_red' ? 'active' : ''}`}
              onClick={() => setUploadSubTab('operador_red')}
            >
              Tarifas Operador de red
            </button>
            <button 
              className={`segmented-btn ${uploadSubTab === 'enerpro' ? 'active' : ''}`}
              onClick={() => setUploadSubTab('enerpro')}
            >
              Plan enerPro
            </button>
          </div>

          {uploadSubTab === 'operador_red' && (
            <>
              <section className="upload-section fade-in">
            <div className="metadata-container">
              <div className="input-group">
                <label>Operador de Red</label>
                <select value={operador} onChange={(e) => setOperador(e.target.value)}>
                  {operadoresSoportados.map(op => <option key={op} value={op}>{op}</option>)}
                </select>
              </div>
              
              <div className="input-group">
                <label>Mes de la Tarifa</label>
                <select value={mes} onChange={(e) => setMes(e.target.value)}>
                  {meses.map(m => <option key={m.num} value={m.num}>{m.name}</option>)}
                </select>
              </div>

              <div className="input-group">
                <label>Año</label>
                <select value={anio} onChange={(e) => setAnio(e.target.value)} className="year-input">
                  {Array.from({ length: 31 }, (_, i) => 2015 + i).map(y => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* ZONA DINÁMICA: PDF para Afinia, CSV para enerBit */}
            {operador === 'Afinia' ? (
              <>
                <form 
                  className={`drag-file-element ${dragActive ? "drag-active" : ""}`}
                  onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop}
                  onSubmit={(e) => e.preventDefault()}
                >
                  <div className="upload-content">
                    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="upload-icon"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                    {file ? (
                      <p className="file-name">✅ Archivo adjunto: <b>{file.name}</b></p>
                    ) : (
                      <p>Arrastra y suelta tu archivo <b>PDF</b> de Afinia aquí o <span className="ul-link">haz click para seleccionarlo</span></p>
                    )}
                    <input type="file" id="input-file-upload" multiple={false} accept=".pdf" onChange={handleChange} />
                  </div>
                </form>

                {error && <div className="error-card">⚠️ Error: {error}</div>}
                {successMessage && <div className="success-card">{successMessage}</div>}

                {awaitingConfirmation ? (
                  <div className="confirmation-card">
                    <p className="confirmation-text">Ya existe un directorio tarifario para <strong>{operador}</strong> en este período. ¿Sobrescribir?</p>
                    <div className="confirmation-actions">
                      <button className="btn btn-outline" onClick={() => { setAwaitingConfirmation(false); setLoading(false); }}>Cancelar</button>
                      <button className="btn btn-danger" onClick={handleUpload}>Confirmar Sobrescritura</button>
                    </div>
                  </div>
                ) : (
                  <button className="btn btn-primary btn-block" onClick={handleUpload} disabled={!file || loading}>
                    {loading ? <span className="loader"></span> : "Procesar PDF y Guardar Registro"}
                  </button>
                )}
              </>
            ) : (
              <>
                <form 
                  className={`drag-file-element ${csvDragActive ? "drag-active" : ""}`}
                  onDragEnter={(e) => { e.preventDefault(); setCsvDragActive(true); }}
                  onDragLeave={(e) => { e.preventDefault(); setCsvDragActive(false); }}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => { e.preventDefault(); setCsvDragActive(false); if (e.dataTransfer.files[0]) setCsvFile(e.dataTransfer.files[0]); }}
                  onSubmit={(e) => e.preventDefault()}
                >
                  <div className="upload-content">
                    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="upload-icon"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>
                    {csvFile ? (
                      <p className="file-name">✅ Archivo adjunto: <b>{csvFile.name}</b></p>
                    ) : (
                      <p>Arrastra y suelta tu archivo <b>CSV</b> de enerBit aquí o <span className="ul-link">haz click para seleccionarlo</span></p>
                    )}
                    <input type="file" id="input-csv-upload" multiple={false} accept=".csv" onChange={(e) => { if (e.target.files[0]) setCsvFile(e.target.files[0]); }} />
                  </div>
                </form>

                {csvError && <div className="error-card">⚠️ Error: {csvError}</div>}
                {csvSuccess && <div className="success-card">{csvSuccess}</div>}

                {csvWarning ? (
                  <div className="confirmation-card">
                    <p className="confirmation-text">Ya existe un registro enerBit para <strong>Afinia</strong> en este período. ¿Sobrescribir?</p>
                    <div className="confirmation-actions">
                      <button className="btn btn-outline" onClick={() => { setCsvWarning(false); setCsvLoading(false); }}>Cancelar</button>
                      <button className="btn btn-danger" onClick={() => handleCsvUpload(true)}>Confirmar Sobrescritura</button>
                    </div>
                  </div>
                ) : (
                  <button className="btn btn-primary btn-block" onClick={() => handleCsvUpload(false)} disabled={!csvFile || csvLoading}>
                    {csvLoading ? <span className="loader"></span> : "Procesar CSV y Guardar Registro"}
                  </button>
                )}
              </>
            )}
          </section>


          {groupedData.length > 0 && (
            <section className="data-section fade-in">
              <div className="data-header-row">
                <div>
                  <h3>Repositorio Tarifario Maestro</h3>
                  <p className="text-subtitle" style={{marginBottom: '2rem'}}>Consolidado histórico de cuadros tarifarios digitalizados.</p>
                </div>
                
                <div className="filters-toolbar">
                  <div className="filter-label-group">
                    <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-muted"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>
                    <span className="font-medium text-muted" style={{fontSize: '0.9rem'}}>Filtrar:</span>
                  </div>
                  <select className="filter-select" value={filterMes} onChange={(e) => setFilterMes(e.target.value)}>
                    <option value="">Todos los Meses</option>
                    {meses.map(m => <option key={m.num} value={m.num}>{m.name}</option>)}
                  </select>
                  <select className="filter-select" value={filterAnio} onChange={(e) => setFilterAnio(e.target.value)}>
                    {Array.from({ length: 31 }, (_, i) => 2015 + i).map(y => (
                      <option key={y} value={y}>{y}</option>
                    ))}
                  </select>
                  <select className="filter-select" value={filterFuente} onChange={(e) => setFilterFuente(e.target.value)}>
                    <option value="todas">Todas las fuentes</option>
                    <option value="afinia">Afinia (OR directo)</option>
                    <option value="enerbit">enerBit → Afinia</option>
                  </select>
                </div>
              </div>
              
              <div className="grouped-documents-list">
                {groupedData.filter(g => {
                   if (filterMes && String(g.mes) !== String(filterMes)) return false;
                   if (filterAnio && String(g.anio) !== String(filterAnio)) return false;
                   return true;
                }).map((docGroup, index) => {
                  const mesName = meses.find(m => m.num == docGroup.mes)?.name || docGroup.mes;
                  return (
                    <article key={index} className="document-card fade-in" style={{ animationDelay: `${index * 0.1}s` }}>
                      <div className="document-card-header">
                        <div className="doc-meta">
                          <span className="doc-operator">⚡️ {docGroup.fuente || docGroup.operador_red}</span>
                          <span className="doc-period">{mesName} {docGroup.anio}</span>
                        </div>
                        <span className="doc-badge">{docGroup.registros.length} niveles extraídos</span>
                      </div>
                      
                      <div className="document-card-body">
                         <div className="table-wrapper local-table-wrapper">
                            <table className="flat-table compact-table">
                              <thead>
                                <tr>
                                  <th>Fila Extraída</th>
                                  <th>G</th>
                                  <th>T</th>
                                  <th>PR</th>
                                  <th>R</th>
                                  <th>D</th>
                                  <th>C</th>
                                  <th>CU</th>
                                  <th>COT</th>
                                  <th>OT</th>
                                </tr>
                              </thead>
                              <tbody>
                                {docGroup.registros.map((row, idx) => (
                                  <tr key={idx}>
                                    <td className="font-medium text-dark min-w-row">{row.Fila || row.fila}</td>
                                    <td>{row.G || row.gen}</td>
                                    <td>{row.T || row.stn}</td>
                                    <td className="text-purple">{row.pr_val !== null && row.pr_val !== undefined ? row.pr_val : "N/A"}</td>
                                    <td>{row.R || row.res}</td>
                                    <td>{row.D || row.d_val}</td>
                                    <td>{row.C || row.c_val}</td>
                                    <td className="font-bold text-dark">{row.CU || row.cu_val}</td>
                                    <td className="font-bold text-enerbit">{row.COT || row.cot_val}</td>
                                    <td className="font-medium">{row.ot_val !== null && row.ot_val !== undefined ? row.ot_val : "N/A"}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                         </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            </section>
          )}
          </>
          )}

          {uploadSubTab === 'enerpro' && (
            <section className="form-section fade-in">
              <div className="form-card">

                <div className="market-section">
                  <div className="section-title-box">
                    <h3>Mercado Residencial y Comercial</h3>
                  </div>

                  {/* Subsección 1: Específico por Operador */}
                  <div className="sub-market-card">
                    <div className="sub-market-header">
                      <h4 className="text-primary font-medium">1. Parámetros por Operador (Anual)</h4>
                      <p className="text-muted" style={{fontSize: '0.85rem', marginTop: '0.2rem'}}>Valores FijaBit atados al comercializador para la vigencia específica.</p>
                    </div>
                    
                    <div className="form-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
                      <div className="input-group">
                        <label>Vigencia (Año)</label>
                        <select className="form-select" value={anioOperador} onChange={(e) => setAnioOperador(e.target.value)}>
                          {Array.from({ length: 31 }, (_, i) => 2015 + i).map(y => <option key={y} value={y}>{y}</option>)}
                        </select>
                      </div>

                      <div className="input-group">
                        <label>Operador de Red</label>
                        <select className="form-select" value={planOperador} onChange={(e) => setPlanOperador(e.target.value)}>
                           {operadoresSoportados.map(op => <option key={op} value={op}>{op}</option>)}
                        </select>
                      </div>

                      <div className="input-group">
                        <label>FijaBit Hogar (2026)</label>
                        <div className="input-prefix"><span className="prefix">$</span><input type="number" placeholder="0.00" className="pl-prefix" value={fijabitHogar} onChange={(e) => setFijabitHogar(e.target.value)} /></div>
                      </div>

                      <div className="input-group">
                        <label>FijaBit Comercial (2026)</label>
                        <div className="input-prefix"><span className="prefix">$</span><input type="number" placeholder="0.00" className="pl-prefix" value={fijabitComercial} onChange={(e) => setFijabitComercial(e.target.value)} /></div>
                      </div>
                    </div>

                    <div className="form-actions" style={{marginTop: '1.5rem', textAlign: 'right', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '1rem'}}>
                       {saveSuccessOp && <span className="text-muted" style={{fontSize: '0.85rem'}}>{saveSuccessOp}</span>}
                       <button className="btn btn-orange" onClick={handleSaveParametros}>Guardar Parámetros de Operador</button>
                    </div>
                  </div>

                  {/* Subsección 2: Medidas Globales */}
                  <div className="sub-market-card mt-4">
                    <div className="sub-market-header">
                      <h4 className="text-primary font-medium">2. Cargos Universales de Medida (Anuales)</h4>
                      <p className="text-muted" style={{fontSize: '0.85rem', marginTop: '0.2rem'}}>Costos operativos regionales por año. Rigen mundialmente para todos los operadores.</p>
                    </div>

                    <div className="form-grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
                      <div className="input-group">
                        <label>Vigencia (Año)</label>
                        <select className="form-select" value={anioGlobal} onChange={(e) => setAnioGlobal(e.target.value)}>
                          {Array.from({ length: 31 }, (_, i) => 2015 + i).map(y => <option key={y} value={y}>{y}</option>)}
                        </select>
                      </div>

                      <div className="input-group">
                        <label>Medida Directa Hogar</label>
                        <div className="input-prefix"><span className="prefix">$</span><input type="number" placeholder="0.00" className="pl-prefix" value={medidaDirectaHogar} onChange={(e) => setMedidaDirectaHogar(e.target.value)} /></div>
                      </div>

                      <div className="input-group">
                        <label>Medida Directa ZC Hogar</label>
                        <div className="input-prefix"><span className="prefix">$</span><input type="number" placeholder="0.00" className="pl-prefix" value={medidaDirectaZc} onChange={(e) => setMedidaDirectaZc(e.target.value)} /></div>
                      </div>

                      <div className="input-group">
                        <label>Semi/Indirecta ZC Hogar</label>
                        <div className="input-prefix"><span className="prefix">$</span><input type="number" placeholder="0.00" className="pl-prefix" value={medidaSemiIndirectaZc} onChange={(e) => setMedidaSemiIndirectaZc(e.target.value)} /></div>
                      </div>

                      <div className="input-group">
                        <label>Medida Directa Comercial</label>
                        <div className="input-prefix"><span className="prefix">$</span><input type="number" placeholder="0.00" className="pl-prefix" value={medidaDirectaComercial} onChange={(e) => setMedidaDirectaComercial(e.target.value)} /></div>
                      </div>

                      <div className="input-group">
                        <label>Semi/Indirecta Comercial</label>
                        <div className="input-prefix"><span className="prefix">$</span><input type="number" placeholder="0.00" className="pl-prefix" value={medidaSemiIndirectaComercial} onChange={(e) => setMedidaSemiIndirectaComercial(e.target.value)} /></div>
                      </div>
                    </div>
                    
                    <div className="form-actions" style={{marginTop: '1.5rem', textAlign: 'right', display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '1rem'}}>
                       {saveSuccessGlobal && <span className="text-muted" style={{fontSize: '0.85rem'}}>{saveSuccessGlobal}</span>}
                       <button className="btn btn-primary" onClick={handleSaveGlobales}>Guardar Medidas Globales</button>
                    </div>
                  </div>

                </div>
                
              </div>
            </section>
          )}

        </div>
      );
    } else if (activeTab === 'resumen') {
      const niveles = ["CU1 Prop, OR", "CU12 Prop, Mixta", "CU1 Prop, Cliente", "CU2", "CU3"];
      const mesData = dashData.find(d => d.mes === Number(dashMes));
      const fmt = (v) => v !== null && v !== undefined ? v.toFixed(2) : '—';
      const cls = (v) => v > 0 ? 'diff-positive' : v < 0 ? 'diff-negative' : '';
      return (
        <div className="tab-content fade-in">
          <div className="module-title">
            <h2>Dashboard Comparativo</h2>
            <p className="text-subtitle">Análisis tarifario enerBit vs {dashOR} (OR)</p>
          </div>

          <section className="upload-section fade-in">
            <div className="metadata-container">
              <div className="input-group">
                <label>Operador de Red</label>
                <select value={dashOR} onChange={(e) => setDashOR(e.target.value)}>
                  <option value="Afinia">Afinia</option>
                </select>
              </div>
              <div className="input-group">
                <label>Mes</label>
                <select value={dashMes} onChange={(e) => setDashMes(e.target.value)}>
                  {meses.map(m => <option key={m.num} value={m.num}>{m.name}</option>)}
                </select>
              </div>
              <div className="input-group">
                <label>Año</label>
                <select value={dashAnio} onChange={(e) => setDashAnio(e.target.value)}>
                  {Array.from({ length: 31 }, (_, i) => 2015 + i).map(y => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
              </div>
            </div>
            {(dashFijabit !== null || dashFijabitCom !== null) && (
              <div style={{display:'flex', alignItems: 'center', gap:'1.5rem', marginTop: '0.8rem', background: 'rgba(249, 115, 22, 0.05)', padding: '0.8rem 1.2rem', borderRadius: '8px', border: '1px dashed rgba(249, 115, 22, 0.2)'}}>
                <div className="doc-badge" style={{background: '#FFF7ED', color: '#C2410C', fontWeight: '700'}}>Año 2026</div>
                {dashFijabit !== null && <p className="text-muted" style={{fontSize: '0.85rem', margin: 0}}>FijaBit Hogar: <strong className="text-dark">${dashFijabit?.toFixed(2)}</strong></p>}
                {dashFijabitCom !== null && <p className="text-muted" style={{fontSize: '0.85rem', margin: 0}}>FijaBit Comercio: <strong className="text-dark">${dashFijabitCom?.toFixed(2)}</strong></p>}
                <span className="text-muted" style={{fontSize: '0.75rem', fontStyle: 'italic', marginLeft: 'auto'}}>* Valores configurados para la vigencia actual.</span>
              </div>
            )}

            {!mesData ? (
              <div className="construction-view" style={{marginTop: '1.5rem', paddingBottom: '0.5rem'}}>
                <p className="text-muted">No hay datos para {meses.find(m => m.num === Number(dashMes))?.name} {dashAnio}.</p>
              </div>
            ) : (
              <div className="grouped-documents-list" style={{marginTop: '2rem'}}>
                <article className="document-card fade-in">
                  <div className="document-card-header">
                    <div className="doc-meta">
                      <span className="doc-operator">📊 Análisis Comparativo: {dashOR} vs enerBit</span>
                      <span className="doc-period">{meses.find(m => m.num === Number(dashMes))?.name} {dashAnio}</span>
                    </div>
                    <span className="doc-badge">Resumen Detallado</span>
                  </div>
                  
                  <div className="document-card-body">
                    <div className="table-wrapper local-table-wrapper">
                      <table className="flat-table compact-table">
                        <thead>
                          <tr>
                            <th style={{textAlign: 'left'}}>Nivel</th>
                            <th>COT {dashOR}</th>
                            <th>COT enerBit</th>
                      <th>Pro Hogar</th>
                      <th>Pro Comercio</th>
                            <th>Dif. Tarifaria</th>
                          </tr>
                        </thead>
                        <tbody>
                          {niveles.map((nivel, i) => {
                            const d = mesData.niveles?.[nivel] || {};
                            return (
                              <tr key={i}>
                                <td className="font-medium text-dark min-w-row" style={{textAlign: 'left'}}>
                                  <strong>{nivel}</strong>
                                </td>
                                <td className="text-dark">{fmt(d.cot_or)}</td>
                                <td className="font-bold text-enerbit">{fmt(d.cot_eb)}</td>
                                <td>{fmt(d.pro_hogar)}</td>
                                <td>{fmt(d.pro_comercio)}</td>
                                <td className={`font-bold diff-cell ${cls(d.diferencia_tarifaria)}`}>
                                  {fmt(d.diferencia_tarifaria)}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </article>
              </div>
            )}
          </section>
        </div>
      );
    } else if (activeTab === 'config') {
      const niveles = ["CU1 Prop, OR", "CU12 Prop, Mixta", "CU1 Prop, Cliente", "CU2", "CU3"];
      const fmt = (v) => v !== null && v !== undefined ? v.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—';
      const currency = (v) => v !== null && v !== undefined ? v.toLocaleString('es-CO', { style: 'currency', currency: 'COP' }) : '—';
      
      const consumo = parseFloat(simConsumo) || 0;
      
      return (
        <div className="tab-content fade-in">
          <div className="module-title">
            <div style={{display: "flex", justifyContent: "space-between"}}>
              <h2>Simulación de Propuesta Comercial</h2>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <input
                  ref={invoiceInputRef}
                  type="file"
                  accept=".pdf"
                  style={{ display: 'none' }}
                  onChange={handleInvoiceExtract}
                />
                <button
                  className="btn btn-outline"
                  style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', padding: '0.5rem 1rem' }}
                  onClick={() => invoiceInputRef.current?.click()}
                  disabled={invoiceLoading}
                >
                  {invoiceLoading ? (
                    <span className="loader" style={{ width: '14px', height: '14px' }}></span>
                  ) : (
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>
                  )}
                  Analizar Factura
                </button>
                {invoiceError && <span style={{ fontSize: '0.8rem', color: '#dc2626' }}>Error: {invoiceError}</span>}
              </div>
            </div>
            <p className="text-subtitle">Proyecta el ahorro potencial del cliente basado en su consumo real y las tarifas vigentes.</p>
          </div>

          <section className="upload-section fade-in">

            <div className="metadata-container">
              <div className="input-group">
                <label>Consumo Promedio Mensual (kWh)</label>
                <div className="input-prefix">
                  <input 
                    type="number"
                    placeholder="Ej: 350"
                    value={simConsumo}
                    onChange={(e) => setSimConsumo(e.target.value)} 
                    onBlur={() => { if (simConsumo === "") setSimConsumo("0"); }}
                    style={{paddingLeft: '1rem'}}
                  />
                </div>
              </div>

              <div className="input-group">
                <label>Nivel de Tensión / Propiedad</label>
                <select value={simNivel} onChange={(e) => setSimNivel(e.target.value)}>
                  {niveles.map(n => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>

              <div className="input-group">
                <label>Vigencia (Año)</label>
                <select value={dashAnio} onChange={(e) => setDashAnio(e.target.value)}>
                  {Array.from({ length: 31 }, (_, i) => 2015 + i).map(y => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
              </div>

              <div className="input-group">
                <label>Mercado</label>
                <select value={simMercado} onChange={(e) => setSimMercado(e.target.value)}>
                  <option value="Hogar">🏠 Residencial (Hogar)</option>
                  <option value="Comercial">🏢 Comercial / Industrial</option>
                </select>
              </div>

              <div className="input-group">
                <label>Estrato</label>
                <select value={simEstrato} onChange={(e) => setSimEstrato(e.target.value)} disabled={simMercado === 'Comercial' || simEsZC === 'Sí'}>
                  {[1, 2, 3, 4, 5, 6].map(s => <option key={s} value={s}>Estrato {s}</option>)}
                </select>
              </div>

              <div className="input-group">
                <label>Factor Múltiplo</label>
                <div className="input-prefix">
                  <input 
                    type="number" 
                    value={simFactor} 
                    onChange={(e) => setSimFactor(e.target.value)} 
                    onBlur={() => { if (simFactor === "") setSimFactor("1"); }}
                    style={{paddingLeft: '1rem'}}
                  />
                </div>
                <p className="text-muted" style={{fontSize: '0.7rem', marginTop: '0.2rem'}}>
                  {simFactor === 1 ? "✓ Medida Directa" : simFactor > 80 ? "✓ Medida Semi/Indirecta" : "—"}
                </p>
              </div>

              <div className="input-group">
                <label>¿Es Zona Común?</label>
                <select 
                  value={simEsZC} 
                  onChange={(e) => setSimEsZC(e.target.value)}
                  disabled={simMercado === 'Comercial'}
                >
                  <option value="No">No</option>
                  <option value="Sí">Sí</option>
                </select>
              </div>
            </div>

            {consumo > 0 ? (
              <div className="grouped-documents-list" style={{marginTop: '2rem'}}>
                <article className="document-card fade-in">
                  <div className="document-card-header">
                    <div className="doc-meta">
                      <span className="doc-operator">📈 Proyección de Costos: {simNivel}</span>
                      <span className="doc-period">Basado en {consumo} kWh/mes</span>
                    </div>
                    <span className="doc-badge" style={{background: '#dcfce7', color: '#166534'}}>Simulación Activa</span>
                  </div>
                  
                  <div className="document-card-body">
                    <div className="table-wrapper local-table-wrapper">
                      <table className="flat-table compact-table">
                        <thead>
                          <tr>
                            <th style={{textAlign: 'left'}}>Mes</th>
                            <th>Tarifa {dashOR}</th>
                            <th>Total {dashOR}</th>
                            <th>Tarifa enerBit</th>
                            <th>Cargo enerPro</th>
                            <th>Total enerBit</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dashData.sort((a, b) => a.mes - b.mes).map((m, idx) => {
                            const d = m.niveles?.[simNivel] || {};
                            
                            // Lógica de Contribución y Mercado
                            // Ajuste: Si es Comercial, ignoramos ZC
                            const actualMercado = simMercado === "Comercial" ? "Comercial" : (simEsZC === "Sí" ? "Hogar" : "Hogar");
                            // Wait, the logic should be: if ZC is YES and Mercado is NOT Comercial (already disabled but for safety)...
                            const isIndustrial = simMercado === "Comercial";
                            const isZC = !isIndustrial && simEsZC === "Sí";
                            
                            const paysContribution = isIndustrial || (!isZC && parseInt(simEstrato) >= 5);
                            const taxRate = paysContribution ? 0.20 : 0.0;
                            
                            // Cargos Globales enerPro
                            let cargoFijo = 0;
                            const factorNum = parseFloat(simFactor) || 0;
                            const isIndirect = factorNum >= 80;

                            if (isZC) {
                                cargoFijo = isIndirect ? (parseFloat(medidaSemiIndirectaZc) || 0) : (parseFloat(medidaDirectaZc) || 0);
                            } else {
                                if (isIndustrial) {
                                    cargoFijo = isIndirect ? (parseFloat(medidaSemiIndirectaComercial) || 0) : (parseFloat(medidaDirectaComercial) || 0);
                                } else {
                                    cargoFijo = parseFloat(medidaDirectaHogar) || 0; 
                                }
                            }

                            const tarifaOR = d.cot_or || 0;
                            const tarifaEB = isIndustrial ? (d.pro_comercio || 0) : (d.pro_hogar || 0);
                            
                            const hasDataEB = tarifaEB > 0;
                            
                            const subtotalOR = tarifaOR * consumo;
                            const subtotalEB = hasDataEB ? tarifaEB * consumo : 0;
                            
                            const totalOR = subtotalOR * (1 + taxRate);
                            const totalEB = hasDataEB ? (subtotalEB * (1 + taxRate)) + cargoFijo : 0;
                            const ahorro = hasDataEB ? totalOR - totalEB : null;
                            
                            return (
                              <tr key={idx}>
                                <td className="font-medium text-dark" style={{textAlign: 'left'}}>
                                  {meses.find(mes => mes.num === m.mes)?.name}
                                </td>
                                <td>{fmt(tarifaOR)}</td>
                                <td className="text-muted">{currency(totalOR)}</td>
                                
                                <td className={`text-enerbit font-bold ${!hasDataEB ? 'text-muted' : ''}`}>{hasDataEB ? fmt(tarifaEB) : "Sin datos"}</td>
                                <td className="text-enerbit">{hasDataEB ? currency(cargoFijo) : "—"}</td>
                                <td className="font-bold text-dark">{hasDataEB ? currency(totalEB) : "—"}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                        {dashData.filter(m => {
                           const d = m.niveles?.[simNivel] || {};
                           const isIndustrial = simMercado === "Comercial";
                           const tarifaEB = isIndustrial ? (d.pro_comercio || 0) : (d.pro_hogar || 0);
                           return tarifaEB > 0;
                        }).length > 0 && (
                           <tfoot>
                              <tr style={{background: '#f8fafc', fontWeight: '900', borderTop: '2px solid var(--primary)'}}>
                                 <td colSpan="2" style={{textAlign: 'right', padding: '1.2rem', color: 'var(--primary)'}}>TOTAL ACUMULADO</td>
                                 <td className="text-muted">
                                    {currency(dashData.reduce((acc, m) => {
                                       const d = m.niveles?.[simNivel] || {};
                                       const isIndustrial = simMercado === "Comercial";
                                       const isZC = !isIndustrial && simEsZC === "Sí";
                                       const tarifaEB = isIndustrial ? (d.pro_comercio || 0) : (d.pro_hogar || 0);
                                       if (tarifaEB <= 0) return acc;
                                       
                                       const paysContribution = isIndustrial || (!isZC && parseInt(simEstrato) >= 5);
                                       const taxRate = paysContribution ? 0.20 : 0.0;
                                       return acc + ((d.cot_or || 0) * consumo * (1 + taxRate));
                                    }, 0))}
                                 </td>
                                 <td colSpan="2" style={{textAlign: 'right'}}></td>
                                 <td className="text-dark">
                                    {currency(dashData.reduce((acc, m) => {
                                       const d = m.niveles?.[simNivel] || {};
                                       const isIndustrial = simMercado === "Comercial";
                                       const isZC = !isIndustrial && simEsZC === "Sí";
                                       const tarifaEB = isIndustrial ? (d.pro_comercio || 0) : (d.pro_hogar || 0);
                                       if (tarifaEB <= 0) return acc;
                                       
                                       const paysContribution = isIndustrial || (!isZC && parseInt(simEstrato) >= 5);
                                       const taxRate = paysContribution ? 0.20 : 0.0;
                                       
                                       let cargoFijo = 0;
                                       const factorNum = parseFloat(simFactor) || 0;
                                       const isIndirect = factorNum >= 80;

                                       if (isZC) cargoFijo = isIndirect ? (parseFloat(medidaSemiIndirectaZc) || 0) : (parseFloat(medidaDirectaZc) || 0);
                                       else if (isIndustrial) cargoFijo = isIndirect ? (parseFloat(medidaSemiIndirectaComercial) || 0) : (parseFloat(medidaDirectaComercial) || 0);
                                       else cargoFijo = parseFloat(medidaDirectaHogar) || 0;
                                       
                                       return acc + (tarifaEB * consumo * (1 + taxRate)) + cargoFijo;
                                    }, 0))}
                                 </td>
                              </tr>
                           </tfoot>
                        )}
                      </table>
                    </div>
                  </div>
                </article>
                
                <div style={{marginTop: '1.5rem', padding: '1.5rem', background: '#f0fdf4', borderRadius: '12px', border: '1px solid #bbf7d0', display: 'flex', alignItems: 'center', gap: '1.5rem'}}>
                   <div style={{background: '#22c55e', color: 'white', width: '56px', height: '56px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.8rem', boxShadow: '0 4px 6px rgba(34, 197, 94, 0.2)'}}>💰</div>
                   <div>
                      <h4 style={{color: '#166534', margin: 0, fontSize: '1.1rem'}}>Propuesta de Valor enerBit</h4>
                      <p style={{color: '#15803d', margin: '0.3rem 0 0 0', fontSize: '1rem', lineHeight: '1.4'}}>
                        Basado en el análisis de los meses con datos, el cliente ahorraría un promedio mensual de <strong style={{fontSize: '1.2rem'}}>{currency(dashData.filter(m => {
                           const d = m.niveles?.[simNivel] || {};
                           const isIndustrial = simMercado === "Comercial";
                           const tarifaEB = isIndustrial ? (d.pro_comercio || 0) : (d.pro_hogar || 0);
                           return tarifaEB > 0;
                        }).reduce((acc, m) => {
                           const d = m.niveles?.[simNivel] || {};
                           const isIndustrial = simMercado === "Comercial";
                           const isZC = !isIndustrial && simEsZC === "Sí";
                           const paysContribution = isIndustrial || (!isZC && parseInt(simEstrato) >= 5);
                           const taxRate = paysContribution ? 0.20 : 0.0;
                           
                           const tarifaOR = d.cot_or || 0;
                           const tarifaEB = isIndustrial ? (d.pro_comercio || 0) : (d.pro_hogar || 0);
                           
                           const subtotalOR = (tarifaOR * consumo) * (1 + taxRate);
                           
                           let cargoFijo = 0;
                           const factorNum = parseFloat(simFactor) || 0;
                           const isIndirect = factorNum >= 80;

                           if (isZC) cargoFijo = isIndirect ? (parseFloat(medidaSemiIndirectaZc) || 0) : (parseFloat(medidaDirectaZc) || 0);
                           else if (isIndustrial) cargoFijo = isIndirect ? (parseFloat(medidaSemiIndirectaComercial) || 0) : (parseFloat(medidaDirectaComercial) || 0);
                           else cargoFijo = parseFloat(medidaDirectaHogar) || 0;

                           const subtotalEB = (tarifaEB * consumo * (1 + taxRate)) + cargoFijo;
                           return acc + (subtotalOR - subtotalEB);
                        }, 0) / (dashData.filter(m => {
                           const d = m.niveles?.[simNivel] || {};
                           const isIndustrial = simMercado === "Comercial";
                           const tarifaEB = isIndustrial ? (d.pro_comercio || 0) : (d.pro_hogar || 0);
                           return tarifaEB > 0;
                        }).length || 1))}</strong>.
                      </p>
                      <div style={{marginTop: '0.6rem', display: 'inline-block', background: '#22c55e', color: 'white', padding: '0.4rem 1rem', borderRadius: '20px', fontWeight: '700', fontSize: '0.95rem'}}>
                         ⚡️ Ahorro estimado del {(() => {
                           const totalOR = dashData.reduce((acc, m) => {
                              const d = m.niveles?.[simNivel] || {};
                              const isIndustrial = simMercado === "Comercial";
                              const isZC = !isIndustrial && simEsZC === "Sí";
                              const tarifaEB = isIndustrial ? (d.pro_comercio || 0) : (d.pro_hogar || 0);
                              if (tarifaEB <= 0) return acc;
                              const paysContribution = isIndustrial || (!isZC && parseInt(simEstrato) >= 5);
                              const taxRate = paysContribution ? 0.20 : 0.0;
                              return acc + ((d.cot_or || 0) * consumo * (1 + taxRate));
                           }, 0);
                           const totalEB = dashData.reduce((acc, m) => {
                              const d = m.niveles?.[simNivel] || {};
                              const isIndustrial = simMercado === "Comercial";
                              const isZC = !isIndustrial && simEsZC === "Sí";
                              const tarifaEB = isIndustrial ? (d.pro_comercio || 0) : (d.pro_hogar || 0);
                              if (tarifaEB <= 0) return acc;
                              
                              const paysContribution = isIndustrial || (!isZC && parseInt(simEstrato) >= 5);
                              const taxRate = paysContribution ? 0.20 : 0.0;
                              
                              let cargoFijo = 0;
                              const factorNum = parseFloat(simFactor) || 0;
                              const isIndirect = factorNum >= 80;

                              if (isZC) cargoFijo = isIndirect ? (parseFloat(medidaSemiIndirectaZc) || 0) : (parseFloat(medidaDirectaZc) || 0);
                              else if (isIndustrial) cargoFijo = isIndirect ? (parseFloat(medidaSemiIndirectaComercial) || 0) : (parseFloat(medidaDirectaComercial) || 0);
                              else cargoFijo = parseFloat(medidaDirectaHogar) || 0;
                              
                              return acc + (tarifaEB * consumo * (1 + taxRate)) + cargoFijo;
                           }, 0);
                           return totalOR > 0 ? (((totalOR - totalEB) / totalOR) * 100).toFixed(1) : "0";
                        })()}% sobre facturación actual
                      </div>
                   </div>
                </div>
              </div>
            ) : (
              <div className="construction-view" style={{height: '300px'}}>
                <svg className="cog-icon" xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
                <p>Ingresa el consumo mensual para generar la simulación.</p>
              </div>
            )}
          </section>
        </div>
      );
    }
  };

  return (
    <div className="app-layout">
      {/* Sidebar Lateral */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <img src="/logo.png" alt="enerBit Logo" className="brand-logo" />
        </div>
        
        <nav className="sidebar-nav">
          <ul>
            <li>
              <button 
                className={`nav-btn ${activeTab === 'upload' ? 'active' : ''}`}
                onClick={() => setActiveTab('upload')}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                <span className="nav-text">Ingesta de Tarifas</span>
              </button>
            </li>
            <li>
              <button 
                className={`nav-btn ${activeTab === 'resumen' ? 'active' : ''}`}
                onClick={() => setActiveTab('resumen')}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>
                <span className="nav-text">Resumen / Dashboard</span>
              </button>
            </li>
            <li>
              <button 
                className={`nav-btn ${activeTab === 'config' ? 'active' : ''}`}
                onClick={() => setActiveTab('config')}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>
                <span className="nav-text">Simulación</span>
              </button>
            </li>
          </ul>
        </nav>
      </aside>

      {/* Contenido Principal */}
      <div className="main-wrapper">
        <header className="top-header">
           <div className="header-content">
             <h1 className="header-title">
               {activeTab === 'upload' && "Administración Central"}
               {activeTab === 'resumen' && "Visualizador Global"}
               {activeTab === 'config' && "Simulador de Propuestas"}
             </h1>
           </div>
        </header>

        <main className="content-container">
          <div className="content-fluid-limit">
            {renderContent()}
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
