import { useState, useEffect, useMemo } from 'react';
import './App.css';

function App() {
  const [activeTab, setActiveTab] = useState('upload'); // 'upload', 'resumen', 'config'

  // Estados del escáner PDF
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState([]);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  const [operador, setOperador] = useState("Afinia");
  const [mes, setMes] = useState(new Date().getMonth() + 1);
  const [anio, setAnio] = useState(new Date().getFullYear());

  const operadoresSoportados = ["Afinia", "Enel"];
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

  const fetchRegistros = () => {
    fetch('http://localhost:8000/registros/')
      .then(res => res.json())
      .then(json => {
        if(Array.isArray(json)) setData(json);
      })
      .catch(err => console.error("Error al cargar historial:", err));
  };

  useEffect(() => {
    fetchRegistros();
  }, []);

  // LÓGICA DE AGRUPACIÓN (UX Mejora: Agrupar por documento)
  const groupedData = useMemo(() => {
    const groups = {};
    data.forEach(row => {
      // Creamos un identificador único para el documento Padre (ej: "Afinia-4-2026")
      const groupKey = `${row.operador_red}-${row.anio}-${row.mes}`;
      if (!groups[groupKey]) {
        groups[groupKey] = {
          operador_red: row.operador_red,
          mes: row.mes,
          anio: row.anio,
          registros: []
        };
      }
      groups[groupKey].registros.push(row);
    });
    
    // Convertir el diccionario a un array y ordenar por fecha reciente (asumiendo que anio/mes determina el orden)
    return Object.values(groups).sort((a, b) => {
      if (b.anio !== a.anio) return b.anio - a.anio;
      return b.mes - a.mes;
    });
  }, [data]);

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

  const renderContent = () => {
    if (activeTab === 'upload') {
      return (
        <div className="tab-content fade-in">
          
          <div className="module-title">
            <h2>Extracción Automática de Tarifas</h2>
            <p className="text-subtitle">Motor de análisis y digitalización de documentos tarifarios expedidos por los Operadores de Red.</p>
          </div>

          <section className="upload-section">
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

            <form 
              className={`drag-file-element ${dragActive ? "drag-active" : ""}`}
              onDragEnter={handleDrag} 
              onDragLeave={handleDrag} 
              onDragOver={handleDrag} 
              onDrop={handleDrop}
              onSubmit={(e) => e.preventDefault()}
            >
              <div className="upload-content">
                <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="upload-icon"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                {file ? (
                  <p className="file-name">✅ Archivo adjunto: <b>{file.name}</b></p>
                ) : (
                  <p>Arrastra y suelta tu archivo PDF aquí o <span className="ul-link">haz click para seleccionarlo</span></p>
                )}
                <input 
                  type="file" 
                  id="input-file-upload" 
                  multiple={false} 
                  accept=".pdf"
                  onChange={handleChange} 
                />
              </div>
            </form>

            {error && <div className="error-card">⚠️ Error: {error}</div>}
            {successMessage && <div className="success-card">{successMessage}</div>}

            {awaitingConfirmation ? (
              <div className="confirmation-card">
                <p className="confirmation-text">
                  Ya existe un directorio tarifario para <strong>{operador}</strong> en este período. 
                  ¿Estás seguro de que deseas sobrescribir los datos actuales?
                </p>
                <div className="confirmation-actions">
                  <button className="btn btn-outline" onClick={() => { setAwaitingConfirmation(false); setLoading(false); }}>Cancelar</button>
                  <button className="btn btn-danger" onClick={handleUpload}>Confirmar Sobrescritura</button>
                </div>
              </div>
            ) : (
              <button 
                className="btn btn-primary btn-block" 
                onClick={handleUpload} 
                disabled={!file || loading}
              >
                {loading ? <span className="loader"></span> : "Procesar y Guardar Registro"}
              </button>
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
                          <span className="doc-operator">⚡️ {docGroup.operador_red}</span>
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
        </div>
      );
    } else if (activeTab === 'resumen') {
      return (
        <div className="tab-content fade-in construction-view">
          <svg className="cog-icon" xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20a8 8 0 1 0 0-16 8 8 0 0 0 0 16Z"></path><path d="M12 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"></path><path d="M12 2v2"></path><path d="M12 22v-2"></path><path d="m17 20.66-1-1.73"></path><path d="M11 10.27 7.53 4.27"></path><path d="m7 20.66 1-1.73"></path><path d="M16.47 4.27 13 10.27"></path><path d="M22 12h-2"></path><path d="M4 12H2"></path><path d="m17 3.34-1 1.73"></path><path d="M11 13.73 7.53 19.73"></path><path d="m7 3.34 1 1.73"></path><path d="M16.47 19.73 13 13.73"></path></svg>
          <h2>Resumen y Dashboard</h2>
          <p>Módulo de visualización geográfica y calculadoras en construcción...</p>
        </div>
      );
    } else if (activeTab === 'config') {
      return (
        <div className="tab-content fade-in construction-view">
          <svg className="cog-icon" xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 22 8.5 22 15.5 12 22 2 15.5 2 8.5 12 2"></polygon><line x1="12" y1="22" x2="12" y2="15.5"></line><polyline points="22 8.5 12 15.5 2 8.5"></polyline><polyline points="2 15.5 12 8.5 22 15.5"></polyline><line x1="12" y1="2" x2="12" y2="8.5"></line></svg>
          <h2>Configuraciones</h2>
          <p>Módulo de gestión de usuarios y parámetros en construcción...</p>
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
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="4" y1="21" x2="4" y2="14"></line><line x1="4" y1="10" x2="4" y2="3"></line><line x1="12" y1="21" x2="12" y2="12"></line><line x1="12" y1="8" x2="12" y2="3"></line><line x1="20" y1="21" x2="20" y2="16"></line><line x1="20" y1="12" x2="20" y2="3"></line><line x1="1" y1="14" x2="7" y2="14"></line><line x1="9" y1="8" x2="15" y2="8"></line><line x1="17" y1="16" x2="23" y2="16"></line></svg>
                <span className="nav-text">Configuración</span>
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
               {activeTab === 'config' && "Ajustes de Sistema"}
             </h1>
             <div className="header-user">Gestor Tarifario</div>
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
