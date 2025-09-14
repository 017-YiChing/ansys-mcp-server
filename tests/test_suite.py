import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

# Import the server components
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ansys_mcp_server import AnsysInterface, server

class TestAnsysInterface:
    
    @pytest.fixture
    def ansys_interface(self):
        return AnsysInterface()
    
    def test_init(self, ansys_interface):
        """Test AnsysInterface initialization"""
        assert isinstance(ansys_interface.working_directory, Path)
        assert ansys_interface.working_directory.exists()
    
    def test_check_ansys_installation_no_modules(self, ansys_interface):
        """Test status check when no Ansys modules are available"""
        with patch.dict('sys.modules', {
            'ansys.fluent.core': None,
            'ansys.mapdl.core': None,
            'ansys.geometry.core': None
        }, clear=False):
            with patch('builtins.__import__', side_effect=ImportError):
                status = ansys_interface.check_ansys_installation()
                assert status["status"] == "not_found"
                assert not any(status["modules"].values())
    
    @patch('ansys.fluent.core.launch_fluent')
    async def test_create_fluent_session_import_error(self, ansys_interface):
        """Test Fluent session creation when PyFluent is not available"""
        with patch.dict('sys.modules', {}, clear=False):
            with patch('builtins.__import__', side_effect=ImportError):
                result = await ansys_interface.create_fluent_session()
                
                assert result["status"] == "error"
                assert "PyFluent not available" in result["message"]
    
    @patch('ansys.mapdl.core.launch_mapdl')
    async def test_create_mapdl_session_success(self, mock_launch, ansys_interface):
        """Test successful MAPDL session creation"""
        mock_session = Mock()
        mock_session.version = "2023 R1"
        mock_session.directory = "/tmp/mapdl"
        mock_launch.return_value = mock_session
        
        with patch.dict('sys.modules', {'ansys.mapdl.core': Mock()}):
            result = await ansys_interface.create_mapdl_session()
            
            assert result["status"] == "success"
            assert result["version"] == "2023 R1"
            assert "session_id" in result
    
    async def test_create_mapdl_session_import_error(self, ansys_interface):
        """Test MAPDL session creation when PyMAPDL is not available"""
        with patch.dict('sys.modules', {}, clear=False):
            with patch('builtins.__import__', side_effect=ImportError):
                result = await ansys_interface.create_mapdl_session()
                
                assert result["status"] == "error"
                assert "PyMAPDL not available" in result["message"]
    
    async def test_read_ansys_file_not_found(self, ansys_interface):
        """Test reading a non-existent file"""
        result = await ansys_interface.read_ansys_file("/non/existent/file.cas")
        
        assert result["status"] == "error"
        assert "File not found" in result["message"]
    
    async def test_read_ansys_file_success(self, ansys_interface):
        """Test successfully reading an Ansys file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.cas', delete=False) as f:
            f.write("! Fluent case file\n")
            f.write("(0 \"Grid:\")\n")
            temp_path = f.name
        
        try:
            result = await ansys_interface.read_ansys_file(temp_path)
            
            assert result["status"] == "success"
            assert result["file_info"]["type"] == "Fluent case/data file"
            assert result["file_info"]["extension"] == ".cas"
        finally:
            os.unlink(temp_path)
    
    async def test_read_ansys_inp_file(self, ansys_interface):
        """Test reading MAPDL input file with content preview"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.inp', delete=False) as f:
            f.write("/PREP7\n")
            f.write("ET,1,SOLID186\n")
            f.write("BLOCK,0,1,0,1,0,1\n")
            temp_path = f.name
        
        try:
            result = await ansys_interface.read_ansys_file(temp_path)
            
            assert result["status"] == "success"
            assert result["file_info"]["type"] == "MAPDL input/database file"
            assert "preview" in result["file_info"]
            assert "/PREP7" in result["file_info"]["preview"]
        finally:
            os.unlink(temp_path)
    
    async def test_run_mapdl_commands_success(self, ansys_interface):
        """Test running MAPDL commands"""
        commands = ["/PREP7", "ET,1,SOLID186", "BLOCK,0,1,0,1,0,1"]
        
        result = await ansys_interface.run_mapdl_commands(commands)
        
        assert result["status"] == "success"
        assert result["commands_executed"] == 3
        assert len(result["results"]) == 3
        assert result["results"][0]["command"] == "/PREP7"


class TestMCPServer:
    
    @pytest.fixture
    async def server_instance(self):
        return server
    
    async def test_list_resources(self, server_instance):
        """Test listing available resources"""
        resources = await server_instance._handlers["list_resources"]()
        
        assert len(resources) >= 2
        resource_uris = [r.uri for r in resources]
        assert "ansys://status" in resource_uris
        assert "ansys://working-directory" in resource_uris
    
    async def test_read_status_resource(self, server_instance):
        """Test reading status resource"""
        with patch.object(AnsysInterface, 'check_ansys_installation') as mock_check:
            mock_check.return_value = {
                "status": "available",
                "modules": {"fluent": True, "mapdl": False}
            }
            
            result = await server_instance._handlers["read_resource"]("ansys://status")
            data = json.loads(result)
            
            assert data["status"] == "available"
            assert data["modules"]["fluent"] is True
    
    async def test_read_working_directory_resource(self, server_instance):
        """Test reading working directory resource"""
        result = await server_instance._handlers["read_resource"]("ansys://working-directory")
        data = json.loads(result)
        
        assert "directory" in data
        assert "files" in data
        assert isinstance(data["files"], list)
    
    async def test_read_unknown_resource(self, server_instance):
        """Test reading unknown resource raises error"""
        with pytest.raises(ValueError, match="Unknown resource"):
            await server_instance._handlers["read_resource"]("ansys://unknown")
    
    async def test_list_tools(self, server_instance):
        """Test listing available tools"""
        tools = await server_instance._handlers["list_tools"]()
        
        tool_names = [t.name for t in tools]
        expected_tools = [
            "check_ansys_status",
            "create_fluent_session",
            "create_mapdl_session",
            "read_ansys_file",
            "run_mapdl_commands"
        ]
        
        for tool in expected_tools:
            assert tool in tool_names
    
    async def test_call_check_ansys_status_tool(self, server_instance):
        """Test calling check_ansys_status tool"""
        with patch.object(AnsysInterface, 'check_ansys_installation') as mock_check:
            mock_check.return_value = {"status": "available"}
            
            result = await server_instance._handlers["call_tool"]("check_ansys_status", {})
            
            assert len(result) == 1
            data = json.loads(result[0].text)
            assert data["status"] == "available"
    
    async def test_call_create_fluent_session_tool(self, server_instance):
        """Test calling create_fluent_session tool"""
        with patch.object(AnsysInterface, 'create_fluent_session') as mock_create:
            mock_create.return_value = {"status": "success", "session_id": 12345}
            
            result = await server_instance._handlers["call_tool"](
                "create_fluent_session", 
                {"precision": "double", "dimension": "3d"}
            )
            
            assert len(result) == 1
            data = json.loads(result[0].text)
            assert data["status"] == "success"
            mock_create.assert_called_once_with(precision="double", dimension="3d")
    
    async def test_call_read_ansys_file_tool(self, server_instance):
        """Test calling read_ansys_file tool"""
        with patch.object(AnsysInterface, 'read_ansys_file') as mock_read:
            mock_read.return_value = {
                "status": "success",
                "file_info": {"path": "/test.cas", "type": "Fluent case/data file"}
            }
            
            result = await server_instance._handlers["call_tool"](
                "read_ansys_file",
                {"file_path": "/test.cas"}
            )
            
            assert len(result) == 1
            data = json.loads(result[0].text)
            assert data["status"] == "success"
            mock_read.assert_called_once_with(file_path="/test.cas")
    
    async def test_call_run_mapdl_commands_tool(self, server_instance):
        """Test calling run_mapdl_commands tool"""
        commands = ["/PREP7", "ET,1,SOLID186"]
        
        with patch.object(AnsysInterface, 'run_mapdl_commands') as mock_run:
            mock_run.return_value = {
                "status": "success",
                "commands_executed": 2,
                "results": [{"command": cmd, "status": "executed"} for cmd in commands]
            }
            
            result = await server_instance._handlers["call_tool"](
                "run_mapdl_commands",
                {"commands": commands}
            )
            
            assert len(result) == 1
            data = json.loads(result[0].text)
            assert data["status"] == "success"
            assert data["commands_executed"] == 2
            mock_run.assert_called_once_with(commands=commands)
    
    async def test_call_unknown_tool_error(self, server_instance):
        """Test calling unknown tool returns error"""
        result = await server_instance._handlers["call_tool"]("unknown_tool", {})
        
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["status"] == "error"
        assert "Unknown tool" in data["message"]
    
    async def test_call_tool_with_exception(self, server_instance):
        """Test tool call handles exceptions gracefully"""
        with patch.object(AnsysInterface, 'check_ansys_installation') as mock_check:
            mock_check.side_effect = Exception("Test error")
            
            result = await server_instance._handlers["call_tool"]("check_ansys_status", {})
            
            assert len(result) == 1
            data = json.loads(result[0].text)
            assert data["status"] == "error"
            assert "Test error" in data["message"]


class TestIntegration:
    
    async def test_full_workflow_simulation(self):
        """Test a complete simulation workflow"""
        interface = AnsysInterface()
        
        # Step 1: Check status
        status = interface.check_ansys_installation()
        assert "status" in status
        
        # Step 2: Create working file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.inp', delete=False) as f:
            f.write("/PREP7\n")
            f.write("! Simple block model\n")
            f.write("ET,1,SOLID186\n")
            f.write("BLOCK,0,1,0,1,0,1\n")
            f.write("ESIZE,0.2\n")
            f.write("VMESH,ALL\n")
            temp_path = f.name
        
        try:
            # Step 3: Read the file
            file_result = await interface.read_ansys_file(temp_path)
            assert file_result["status"] == "success"
            assert "PREP7" in file_result["file_info"]["preview"]
            
            # Step 4: Execute commands
            commands = [
                "/PREP7",
                "ET,1,SOLID186",
                "BLOCK,0,1,0,1,0,1"
            ]
            
            cmd_result = await interface.run_mapdl_commands(commands)
            assert cmd_result["status"] == "success"
            assert cmd_result["commands_executed"] == 3
            
        finally:
            os.unlink(temp_path)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])_success(self, mock_launch, ansys_interface):
        """Test successful Fluent session creation"""
        mock_session = Mock()
        mock_launch.return_value = mock_session
        
        with patch.dict('sys.modules', {'ansys.fluent.core': Mock()}):
            result = await ansys_interface.create_fluent_session("double", "3d")
            
            assert result["status"] == "success"
            assert result["precision"] == "double"
            assert result["dimension"] == "3d"
            assert "session_id" in result
    
    async def test_create_fluent_session