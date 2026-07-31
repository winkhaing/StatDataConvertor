# Third-party notices

StatData Converter is licensed under Apache License 2.0. It uses open-source
dependencies under their respective licenses.

Notable runtime dependencies include:

- pandas — BSD 3-Clause
- NumPy — BSD 3-Clause
- openpyxl — MIT
- xlrd — BSD
- pyreadstat — Apache License 2.0
- rdata — MIT
- JMPReader.jl-derived native reader — MIT
- MathWorks MATLAB Reader for EViews Workfile-derived WF1 reader — BSD 3-Clause
- React — MIT
- Tauri — Apache License 2.0 and MIT

Release builds use PyInstaller under the GNU General Public License with its
exception for distributing bundled applications.

RDS and RData conversion uses the MIT-licensed `rdata` Python package. R is not
bundled and is not required for those formats.

Legacy Minitab Portable input can call a separately installed local copy of R
and the recommended `foreign` package. Neither R nor `foreign` is bundled with
this project.

The built-in JMP reader is a Python adaptation of JMPReader.jl 0.2.2,
Copyright (C) 2024 Jaakko Ruohio, under the MIT License. Its license text is
included in `licenses/JMPReader-MIT.txt`. The upstream project and its fixtures
are available at https://github.com/jaakkor2/JMPReader.jl.

The built-in EViews WF1 reader adapts file-layout and compression logic from
MathWorks' MATLAB Reader for EViews Workfile, Copyright (c) 2026, The
MathWorks, Inc., under the BSD 3-Clause License. Its license is included in
`licenses/MathWorks-EViews-Reader-BSD-3-Clause.txt`, and the upstream project is
available at
https://github.com/mathworks/MATLAB-Reader-for-EViews-Workfile.

The optional JMP writing bridge controls a separately installed, locally
licensed copy of JMP through JSL. JMP is proprietary software and is not
included or redistributed.

The optional SAS bridge controls a separately installed, locally licensed SAS
Foundation runtime in batch mode. The optional Minitab and Statistica bridges
control separately installed, locally licensed Windows applications through
their COM automation interfaces. None of those vendor products, runtimes, or
licenses is included or redistributed.

The StatConverter project was studied as prior art, but its source code is not
included because its academic, non-commercial license is incompatible with the
goals of this Apache-2.0 project.

This file is a practical summary, not a substitute for the license texts shipped
by each dependency.
