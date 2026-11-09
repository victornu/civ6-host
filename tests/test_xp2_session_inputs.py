"""Keep the witnessed input closure when moving its selector into the host."""
import ast,copy,hashlib,inspect,json,unittest,zipfile
from pathlib import Path
from civ6_host.runtime import xp2_session_inputs as inputs
from civ6_host.runtime.paths import resource_root
import qualify_xp1_configuration as qualifier


class XP2SessionInputs(unittest.TestCase):
    @staticmethod
    def _without_host_selection(node):
        """Remove only the historical two-statement host choice and its current guard."""
        node=copy.deepcopy(node)

        def prune(items):
            kept=[]
            for item in items:
                if isinstance(item,ast.ImportFrom) and any(
                        alias.name=='xp2_bbg_inputs' for alias in item.names):
                    continue
                if isinstance(item,ast.Assign) and any(
                        isinstance(target,ast.Name) and target.id in
                        ('bbg_capture','stock_current','host')
                        for target in item.targets):
                    continue
                if isinstance(item,ast.If):
                    test=ast.unparse(item.test)
                    if ('execution_image is not None' in test
                            and ('bbg.is_reference' in test or 'bbg_capture' in test)):
                        continue
                for field,value in ast.iter_fields(item):
                    if isinstance(value,list) and value and all(isinstance(child,ast.stmt) for child in value):
                        setattr(item,field,prune(value))
                kept.append(item)
            return kept

        node.body=prune(node.body)
        return node

    def test_host_delta_preserves_preedit_ast_and_prior_dependency_expansion(self):
        before_path=(Path(__file__).resolve().parents[3]/'outputs/civ6-rl-lab/work/'
            'bbg751-turn-source-scope/war-confirmation/major-dialogue/before/'
            '4427d17ba4db828bff45863eb13234b93e40e36437c861cc6dfb7ebfa98cff2b/'
            'xp2_session_inputs.py')
        before_raw=before_path.read_bytes()
        self.assertEqual(hashlib.sha256(before_raw).hexdigest(),
            '4427d17ba4db828bff45863eb13234b93e40e36437c861cc6dfb7ebfa98cff2b')
        before=next(n for n in ast.parse(before_raw).body if isinstance(n,ast.FunctionDef)
            and n.name=='xp2_saved_load_source_dependencies')
        current=ast.parse(inspect.getsource(inputs.xp2_saved_load_source_dependencies)).body[0]
        self.assertEqual(ast.dump(self._without_host_selection(before)),
                         ast.dump(self._without_host_selection(current)))

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
        self.assertEqual([arg.arg for arg in old.args.kwonlyargs],
                         ['postload160','observe_player'])
        self.assertIs(qualifier.xp2_saved_load_source_dependencies,inputs.xp2_saved_load_source_dependencies)
        retained=json.loads((run/'executed-source-pins.json').read_bytes())
        self.assertEqual(inputs.XP2_UI_HOST[1],retained['native_host']['sha256'])
        current_pins=inputs.xp2_saved_load_source_dependencies(postload160=True,observe_player=True)
        self.assertTrue(all(current_pins.get(path)==expected
                            for path,expected in retained['dependencies'].items()))
        self.assertEqual(len(current_pins)-len(retained['dependencies']),25,
            'The retained 316-pin map predates this 25-source dependency expansion.')


if __name__=='__main__':unittest.main()
