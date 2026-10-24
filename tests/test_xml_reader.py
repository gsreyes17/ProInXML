from decimal import Decimal
from pathlib import Path
import unittest
import re
from xml.etree.ElementTree import ParseError

from defusedxml.common import DefusedXmlException

from app.xml_reader import canonical_source, content_hash, iter_records

SAMPLE = Path(__file__).parent / "fixtures" / "mef_partial_fixture.xml"
URL = ("http://s3.mef.gob.pe/servicios/WSPCM/SG/gastopipsg-old.asmx/"
       "ObtenerDataGastoPIP_old_2?anoEje=2020&nivelGobierno=E&sec_ejec=3")


class XmlReaderTests(unittest.TestCase):
    def setUp(self):
        self.data = SAMPLE.read_bytes()
        self.source = canonical_source(URL)

    def test_preserves_codes_month_zero_and_exact_decimal(self):
        result = list(iter_records(self.data, self.source))
        self.assertEqual(len(result), 7)
        self.assertEqual(result[0]["IdSector"], "01")
        self.assertEqual(result[0]["IdMeta"], "00001")
        self.assertEqual(result[0]["MesEje"], 0)
        self.assertEqual(result[2]["Certificado"], Decimal("110191.37"))
        self.assertEqual(len(result[0]), 39)

    def test_rejects_truncated_document(self):
        with self.assertRaises(ParseError):
            list(iter_records(self.data.replace(b"</DataGasto>", b""), self.source))

    def test_rejects_wrong_source(self):
        source = dict(self.source, unit=5)
        with self.assertRaisesRegex(ValueError, "no coincide"):
            list(iter_records(self.data, source))

    def test_rejects_wrong_namespace(self):
        with self.assertRaises(ValueError):
            list(iter_records(self.data.replace(b"http://www.mef.gob.pe/", b"urn:other"), self.source))

    def test_rejects_missing_field(self):
        with self.assertRaisesRegex(ValueError, "Contrato XML"):
            list(iter_records(self.data.replace(b"<MesEje>0</MesEje>", b"", 1), self.source))

    def test_rejects_duplicate_field(self):
        with self.assertRaisesRegex(ValueError, "repetido"):
            list(iter_records(self.data.replace(b"<MesEje>0</MesEje>", b"<MesEje>0</MesEje>"*2, 1), self.source))

    def test_rejects_loss_of_decimal_precision(self):
        with self.assertRaises(ValueError):
            list(iter_records(self.data.replace(b"<PIA>1800</PIA>", b"<PIA>1.12345</PIA>"), self.source))

    def test_rejects_dtd_and_entities(self):
        data = b'<!DOCTYPE DataGasto [<!ENTITY x "text">]>' + self.data
        with self.assertRaises(DefusedXmlException):
            list(iter_records(data, self.source))

    def test_canonicalizes_query_order(self):
        reordered = URL.split("?")[0]+"?sec_ejec=3&nivelGobierno=E&anoEje=2020"
        self.assertEqual(canonical_source(reordered), self.source)

    def test_rejects_other_hosts_and_duplicate_parameters(self):
        for url in (URL.replace("s3.mef.gob.pe", "localhost"), URL+"&anoEje=2020"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                canonical_source(url)

    def test_identical_document_has_identical_hash(self):
        self.assertEqual(content_hash(self.data), content_hash(bytes(self.data)))
        self.assertNotEqual(content_hash(self.data), content_hash(self.data+b" "))

    def test_optional_unit_variants_and_mixed_records(self):
        for replacement, code in [(b'<Unidad_Medida/>','UNIDAD_VACIA'),
                                  (b'<Unidad_Medida>  </Unidad_Medida>','UNIDAD_VACIA'),
                                  (b'','UNIDAD_AUSENTE'),
                                  (b'<Unidad_Medida xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:nil="true"/>','UNIDAD_NIL')]:
            with self.subTest(code=code,replacement=replacement):
                changed = re.sub(rb'<Unidad_Medida>.*?</Unidad_Medida>',replacement,self.data,count=1)
                obs=[]
                result=list(iter_records(changed,self.source,obs))
                self.assertEqual(len(result),7)
                self.assertIsNone(result[0]['Unidad_Medida'])
                self.assertIsNotNone(result[1]['Unidad_Medida'])
                self.assertEqual(obs[0]['codigo'],code)
                self.assertEqual(obs[0]['severidad'],'Advertencia')

    def test_invalid_type_is_an_error_observation(self):
        data=self.data.replace(b'<TipoActProy>3</TipoActProy>',b'<TipoActProy>4</TipoActProy>',1)
        if data==self.data:
            data=self.data.replace(b'<TipoActProy>2</TipoActProy>',b'<TipoActProy>4</TipoActProy>',1)
        obs=[]
        with self.assertRaisesRegex(ValueError,'TipoActProy'):
            list(iter_records(data,self.source,obs))
        self.assertEqual(obs[0]['severidad'],'Error')
        self.assertEqual(len(list(iter_records(data,self.source,[],accept_quality_errors=True))),7)

    def test_real_unit_preserves_leading_zero(self):
        data=re.sub(rb'<Unidad_Medida>.*?</Unidad_Medida>',b'<Unidad_Medida>036</Unidad_Medida>',self.data,count=1)
        self.assertEqual(next(iter_records(data,self.source))['Unidad_Medida'],'036')


if __name__ == "__main__":
    unittest.main()
