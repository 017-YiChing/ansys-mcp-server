#!/usr/bin/env python3
"""
Example: Using Ansys MCP Server with MAPDL
This example demonstrates structural analysis workflow using MAPDL through MCP.
"""

import asyncio
import json
from pathlib import Path

class MockMCPClient:
    """Mock MCP client for demonstration"""
    
    def __init__(self):
        from ansys_mcp_server import AnsysInterface
        self.ansys_interface = AnsysInterface()
    
    async def call_tool(self, tool_name: str, arguments: dict):
        """Simulate MCP tool call"""
        if tool_name == "check_ansys_status":
            return self.ansys_interface.check_ansys_installation()
        elif tool_name == "create_mapdl_session":
            return await self.ansys_interface.create_mapdl_session(
                run_location=arguments.get("run_location")
            )
        elif tool_name == "run_mapdl_commands":
            return await self.ansys_interface.run_mapdl_commands(
                commands=arguments["commands"]
            )
        elif tool_name == "read_ansys_file":
            return await self.ansys_interface.read_ansys_file(
                file_path=arguments["file_path"]
            )
        else:
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}

async def simple_beam_analysis():
    """Simple cantilever beam analysis example"""
    
    print("=== MAPDL Cantilever Beam Analysis ===\n")
    
    client = MockMCPClient()
    
    # Step 1: Check MAPDL availability
    print("1. Checking MAPDL availability...")
    status = await client.call_tool("check_ansys_status", {})
    print(f"MAPDL available: {status.get('modules', {}).get('mapdl', False)}\n")
    
    # Step 2: Create MAPDL session
    print("2. Creating MAPDL session...")
    session_result = await client.call_tool("create_mapdl_session", {})
    print(f"Session: {json.dumps(session_result, indent=2)}\n")
    
    # Step 3: Define analysis commands
    preprocessing_commands = [
        "! Cantilever Beam Analysis",
        "/TITLE, Cantilever Beam Under Point Load",
        "/PREP7",
        "",
        "! Material properties (Steel)",
        "MP,EX,1,200e9     ! Young's modulus (Pa)",
        "MP,PRXY,1,0.3     ! Poisson's ratio",
        "MP,DENS,1,7850    ! Density (kg/m3)",
        "",
        "! Element type",
        "ET,1,SOLID186     ! 3D 20-node structural solid",
        "",
        "! Geometry - Simple beam",
        "BLOCK,0,1,0,0.1,0,0.1  ! 1m long, 0.1x0.1m cross-section",
        "",
        "! Material assignment",
        "VATT,1,1,1        ! Volume attributes",
        "",
        "! Meshing",
        "ESIZE,0.05        ! Element size",
        "VMESH,ALL         ! Mesh all volumes",
        "",
        "! Boundary conditions",
        "ASEL,S,LOC,X,0    ! Select area at x=0",
        "DA,ALL,ALL,0      ! Fix all DOFs at x=0",
        "ALLSEL,ALL",
        "",
        "! Applied loads",
        "NSEL,S,LOC,X,1    ! Select nodes at x=1 (free end)",
        "NSEL,R,LOC,Y,0.05 ! Refine selection to center",
        "NSEL,R,LOC,Z,0.05",
        "F,ALL,FY,-1000    ! Apply 1000N downward force",
        "ALLSEL,ALL"
    ]
    
    solution_commands = [
        "! Solution phase",
        "/SOLU",
        "ANTYPE,STATIC     ! Static analysis",
        "SOLVE             ! Solve",
        "FINISH"
    ]
    
    postprocessing_commands = [
        "! Post-processing",
        "/POST1",
        "PLNSOL,U,SUM      ! Plot total displacement",
        "PLNSOL,S,EQV      ! Plot equivalent stress",
        "",
        "! Get maximum values",
        "*GET,UMAX,PLNSOL,0,MAX",
        "*GET,SMAX,PLNSOL,0,MAX",
        "",
        "! Write results to file",
        "PRESOL,U,SUM      ! Print displacements",
        "PRESOL,S,EQV      ! Print stresses"
    ]
    
    # Step 4: Execute preprocessing
    print("3. Running preprocessing commands...")
    prep_result = await client.call_tool("run_mapdl_commands", {
        "commands": preprocessing_commands
    })
    print(f"Preprocessing: {prep_result['status']} - {prep_result['commands_executed']} commands\n")
    
    # Step 5: Execute solution
    print("4. Running solution...")
    sol_result = await client.call_tool("run_mapdl_commands", {
        "commands": solution_commands
    })
    print(f"Solution: {sol_result['status']} - {sol_result['commands_executed']} commands\n")
    
    # Step 6: Execute post-processing
    print("5. Running post-processing...")
    post_result = await client.call_tool("run_mapdl_commands", {
        "commands": postprocessing_commands
    })
    print(f"Post-processing: {post_result['status']} - {post_result['commands_executed']} commands\n")
    
    print("Analysis complete! Results would be available in MAPDL database.")

async def modal_analysis_example():
    """Modal analysis example for natural frequency calculation"""
    
    print("\n=== MAPDL Modal Analysis ===\n")
    
    client = MockMCPClient()
    
    modal_commands = [
        "! Modal Analysis Setup",
        "/TITLE, Modal Analysis - Cantilever Beam",
        "/PREP7",
        "",
        "! Material properties",
        "MP,EX,1,200e9     ! Steel Young's modulus",
        "MP,DENS,1,7850    ! Steel density",
        "MP,PRXY,1,0.3     ! Poisson's ratio",
        "",
        "! Geometry and meshing (same as before)",
        "ET,1,SOLID186",
        "BLOCK,0,2,0,0.1,0,0.05  ! Longer, thinner beam",
        "VATT,1,1,1",
        "ESIZE,0.1",
        "VMESH,ALL",
        "",
        "! Boundary conditions - Fixed at one end",
        "ASEL,S,LOC,X,0",
        "DA,ALL,ALL,0",
        "ALLSEL,ALL",
        "",
        "! Modal analysis settings",
        "/SOLU",
        "ANTYPE,MODAL      ! Modal analysis",
        "MODOPT,LANB,10    ! Block Lanczos, 10 modes",
        "EQSLV,SPAR        ! Sparse solver",
        "MXPAND,10         ! Expand 10 modes",
        "SOLVE",
        "FINISH",
        "",
        "! Post-processing - Extract frequencies",
        "/POST1",
        "*GET,FREQ1,MODE,1,FREQ",
        "*GET,FREQ2,MODE,2,FREQ", 
        "*GET,FREQ3,MODE,3,FREQ",
        "",
        "! Display mode shapes",
        "SET,1,1           ! First mode",
        "PLDISP,1          ! Plot mode shape",
        "",
        "! Print frequency summary",
        "PRESOL,FREQ"
    ]
    
    print("Executing modal analysis commands...")
    result = await client.call_tool("run_mapdl_commands", {
        "commands": modal_commands
    })
    
    print(f"Modal analysis: {result['status']}")
    print(f"Commands executed: {result['commands_executed']}")
    
    print("\nTypical results would include:")
    print("- Natural frequencies (Hz)")
    print("- Mode shapes visualization") 
    print("- Participation factors")
    print("- Modal mass/stiffness matrices")

async def create_input_file_example():
    """Example of creating and reading MAPDL input file"""
    
    print("\n=== Creating MAPDL Input File ===\n")
    
    # Create comprehensive input file
    input_content = """! MAPDL Input File - Pressure Vessel Analysis
/TITLE, Pressure Vessel Under Internal Pressure
/PREP7

! ===== MATERIAL PROPERTIES =====
MP,EX,1,200e9      ! Young's modulus (Pa) - Steel
MP,PRXY,1,0.3      ! Poisson's ratio
MP,DENS,1,7850     ! Density (kg/m3)

! ===== ELEMENT TYPES =====
ET,1,SOLID186      ! 3D 20-node structural solid
KEYOPT,1,2,1       ! Enhanced strain formulation

! ===== GEOMETRY =====
! Create cylindrical pressure vessel
CYL4,0,0,0.5,0,0,1    ! Inner cylinder
CYL4,0,0,0.6,0,0,1    ! Outer cylinder  

! Create volume by Boolean operations
VSBV,2,1           ! Subtract inner from outer

! ===== MESHING =====
! Material assignment
VATT,1,1,1         ! Volume 1, Material 1, Element type 1

! Mesh sizing
VSEL,S,VOLU,,1     ! Select the vessel volume
ESIZE,0.02         ! Element size
MSHKEY,1           ! Mapped meshing where possible
VMESH,ALL          ! Mesh all selected volumes
ALLSEL,ALL

! ===== BOUNDARY CONDITIONS =====
! Symmetry conditions (if applicable)
ASEL,S,LOC,Z,0     ! Select bottom face
DA,ALL,UZ,0        ! Constrain Z displacement
ALLSEL,ALL

! Pressure loading
ASEL,S,LOC,X,0.5   ! Select inner surface (at radius 0.5)
ASEL,R,LOC,Y,0     ! Refine selection
SF,ALL,PRES,10e6   ! Apply 10 MPa internal pressure
ALLSEL,ALL

! ===== SOLUTION =====
/SOLU
ANTYPE,STATIC      ! Static analysis
PSTRES,ON          ! Calculate presstress effects
NLGEOM,OFF         ! Linear geometry (small deformation)

! Solution control
AUTOTS,ON          ! Automatic time stepping
NSUBST,10          ! Number of substeps
OUTRES,ALL,ALL     ! Output all results

SOLVE              ! Solve the problem
SAVE               ! Save the database

! ===== POST-PROCESSING =====
/POST1

! Displacement results
PLNSOL,U,SUM,2,1   ! Plot total displacement, deformed shape
PLNSOL,U,X,0,1     ! Plot X displacement
PLNSOL,U,Y,0,1     ! Plot Y displacement

! Stress results  
PLNSOL,S,X,0,1     ! Plot X stress
PLNSOL,S,Y,0,1     ! Plot Y stress
PLNSOL,S,EQV,2,1   ! Plot equivalent (von Mises) stress

! Get maximum values
*GET,UMAX,PLNSOL,0,MAX  ! Maximum displacement
*GET,SMAX,PLNSOL,0,MAX  ! Maximum stress

! Safety factor calculation
*SET,YIELD_STRENGTH,250e6  ! Material yield strength (Pa)
*SET,SAFETY_FACTOR,YIELD_STRENGTH/SMAX

! Print summary results
/COM,
/COM, ===== ANALYSIS RESULTS SUMMARY =====
/COM, Maximum Displacement: %UMAX% m
/COM, Maximum von Mises Stress: %SMAX% Pa  
/COM, Safety Factor: %SAFETY_FACTOR%
/COM,

! Write results to output file
PRESOL,U,SUM       ! Print displacement summary
PRESOL,S,EQV       ! Print stress summary

FINISH"""
    
    client = MockMCPClient()
    
    # Write input file
    input_file = Path("pressure_vessel.inp")
    with open(input_file, 'w') as f:
        f.write(input_content)
    
    try:
        print("Created MAPDL input file: pressure_vessel.inp")
        
        # Read and analyze the file
        file_result = await client.call_tool("read_ansys_file", {
            "file_path": str(input_file)
        })
        
        print(f"\nFile analysis:")
        print(f"Type: {file_result['file_info']['type']}")
        print(f"Size: {file_result['file_info']['size']} bytes")
        print(f"Extension: {file_result['file_info']['extension']}")
        
        if 'preview' in file_result['file_info']:
            print(f"\nContent preview:")
            print(file_result['file_info']['preview'])
        
        print(f"\nThis input file contains:")
        print("- Material definition for steel")
        print("- 3D solid element type (SOLID186)")
        print("- Cylindrical pressure vessel geometry")
        print("- Mesh generation commands")
        print("- Internal pressure boundary condition")
        print("- Static analysis solution")
        print("- Comprehensive post-processing")
        print("- Safety factor calculation")
        
    finally:
        if input_file.exists():
            input_file.unlink()

async def optimization_example():
    """Design optimization example using MAPDL"""
    
    print("\n=== MAPDL Design Optimization Example ===\n")
    
    optimization_commands = [
        "! Design Optimization - Minimize Weight Subject to Stress Constraint",
        "/TITLE, Bracket Optimization",
        "/PREP7",
        "",
        "! Define design variables",
        "*SET,THICKNESS,0.005  ! Initial thickness (5mm)",
        "*SET,WIDTH,0.050      ! Initial width (50mm)",
        "*SET,HEIGHT,0.100     ! Height parameter",
        "",
        "! Parametric geometry creation",
        "K,1,0,0,0",
        "K,2,WIDTH,0,0",
        "K,3,WIDTH,HEIGHT,0",
        "K,4,0,HEIGHT,0",
        "",
        "A,1,2,3,4              ! Create area",
        "VEXT,ALL,,,,,THICKNESS ! Extrude to create volume",
        "",
        "! Material properties",
        "MP,EX,1,70e9           ! Aluminum Young's modulus",
        "MP,PRXY,1,0.33         ! Poisson's ratio",
        "MP,DENS,1,2700         ! Density",
        "",
        "! Element type and meshing", 
        "ET,1,SOLID186",
        "VATT,1,1,1",
        "ESIZE,0.005",
        "VMESH,ALL",
        "",
        "! Boundary conditions",
        "ASEL,S,LOC,X,0         ! Fix one end",
        "DA,ALL,ALL,0",
        "ALLSEL,ALL",
        "",
        "ASEL,S,LOC,Y,HEIGHT    ! Apply load at top",
        "SFA,ALL,1,PRES,-1000   ! 1000 Pa downward pressure",
        "ALLSEL,ALL",
        "",
        "! Solution",
        "/SOLU",
        "ANTYPE,STATIC",
        "SOLVE",
        "FINISH",
        "",
        "! Optimization setup",
        "/OPT",
        "",
        "! Define design variables",
        "OPVAR,THICKNESS,DV,0.002,0.010  ! Thickness: 2-10mm",
        "OPVAR,WIDTH,DV,0.020,0.080      ! Width: 20-80mm", 
        "",
        "! Define objective function (minimize volume/weight)",
        "*GET,VOLUME,GEOM,VOLU,1,GEOM,VOLU",
        "OPOBJ,VOLUME,MIN",
        "",
        "! Define constraint (max stress < 100 MPa)",
        "*GET,MAX_STRESS,PLNSOL,0,MAX",
        "OPCONS,MAX_STRESS,LE,100e6",
        "",
        "! Run optimization",
        "OPTYPE,SUBP            ! Subproblem approximation",
        "OPFRST,1,10            ! First design cycle, max 10 iterations",
        "OPEXE                  ! Execute optimization",
        "",
        "FINISH"
    ]
    
    client = MockMCPClient()
    
    print("Design optimization workflow:")
    result = await client.call_tool("run_mapdl_commands", {
        "commands": optimization_commands
    })
    
    print(f"Optimization setup: {result['status']}")
    print(f"Commands executed: {result['commands_executed']}")
    
    print("\nOptimization process includes:")
    print("- Design variables: thickness, width")
    print("- Objective: minimize weight (volume)")
    print("- Constraint: maximum stress ≤ 100 MPa")
    print("- Method: subproblem approximation")
    print("- Result: optimal dimensions for minimum weight design")

if __name__ == "__main__":
    asyncio.run(simple_beam_analysis())
    asyncio.run(modal_analysis_example())
    asyncio.run(create_input_file_example())
    asyncio.run(optimization_example())