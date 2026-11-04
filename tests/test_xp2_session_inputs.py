"""Keep the witnessed input closure when moving its selector into the host."""
import ast,hashlib,inspect,json,unittest,zipfile
from civ6_host.runtime import xp2_session_inputs as inputs
from civ6_host.runtime.paths import resource_root
import qualify_xp1_configuration as qualifier


class XP2SessionInputs(unittest.TestCase):
    def test_shared_selector_is_the_existing_witnessed_function(self):
        run=resource_root()/'work/native-xp2-saved-load/run-20261102T123739Z-2187ab257657'
        archive=run/'executed-sources.zip'
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),
            '65943a7613f0c355fa95a5ab6d5586a2a446df8dffa8d828b6ba6a4b75fcdc3d')
        with zipfile.ZipFile(archive) as z:
            names=[name for name in z.namelist() if name.endswith('/qualify_xp1_configuration.py')]
            self.assertEqual(len(names),1)
            tree=ast.parse(z.read(names[0]))
        old=next(n for n in tree.body if isinstance(n,ast.FunctionDef)
            and n.name=='xp2_saved_load_source_dependencies')
        current=ast.parse(inspect.getsource(inputs.xp2_saved_load_source_dependencies)).body[0]
        self.assertEqual(ast.dump(old),ast.dump(current))
        self.assertIs(qualifier.xp2_saved_load_source_dependencies,inputs.xp2_saved_load_source_dependencies)
        retained=json.loads((run/'executed-source-pins.json').read_bytes())
        self.assertEqual(inputs.XP2_UI_HOST[1],retained['native_host']['sha256'])
        self.assertEqual(inputs.xp2_saved_load_source_dependencies(postload160=True,observe_player=True),
                         retained['dependencies'])


if __name__=='__main__':unittest.main()
