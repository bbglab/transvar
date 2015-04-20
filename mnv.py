""" annotate block substitution,
assume this does not affect splice site """
from err import *
from record import *
from transcripts import *
from describe import *
from insertion import taa_set_ins
from deletion import taa_set_del

def annotate_mnv_cdna(args, q, tpts, db):

    found = False
    for t in tpts:
        try:

            if q.tpt and t.name != q.tpt:
                raise IncompatibleTranscriptError("Transcript name unmatched")
            t.ensure_seq()

            r = Record()
            r.chrm = t.chrm
            r.tname = t.format()
            r.gene = t.gene.name
            r.strand = t.strand

            t.ensure_position_array()
            check_exon_boundary(t.np, q.beg)
            check_exon_boundary(t.np, q.end)

            _gnuc_beg = t.tnuc2gnuc(q.beg)
            _gnuc_end = t.tnuc2gnuc(q.end)
            gnuc_beg = min(_gnuc_beg, _gnuc_end)
            gnuc_end = max(_gnuc_beg, _gnuc_end)
            r.pos = '%d-%d' % (gnuc_beg, gnuc_end)

            gnuc_refseq = faidx.getseq(t.chrm, gnuc_beg, gnuc_end)
            tnuc_refseq = reverse_complement(gnuc_refseq) if t.strand == '-' else gnuc_refseq
            gnuc_altseq = reverse_complement(q.altseq) if t.strand == '-' else q.altseq
            if q.refseq and tnuc_refseq != q.refseq:
                raise IncompatibleTranscriptError()

            r.gnuc_range = '%d_%d%s>%s' % (gnuc_beg, gnuc_end, gnuc_refseq, gnuc_altseq)
            r.tnuc_range = '%s_%s%s>%s' % (q.beg, q.end, tnuc_refseq, q.altseq)

            r.reg = describe_genic(args, t.chrm, gnuc_beg, gnuc_end, t, db)
            expt = r.set_splice()
            if (not expt) and r.reg.entirely_in_cds():
                try:
                    tnuc_mnv_coding(t, q.beg.pos, q.end.pos, q.altseq, r)
                except IncompatibleTranscriptError as inst:
                    _beg, _end, _seqlen = inst
                    r.append_info('mnv_(%s-%s)_at_truncated_refseq_of_length_%d' % (_beg, _end, _seqlen))

        except IncompatibleTranscriptError:
            continue
        except SequenceRetrievalError:
            continue
        except UnknownChromosomeError:
            continue
        found = True
        r.format(q.op)

    if not found:
        r = Record()
        r.append_info('no_valid_transcript_found_(from_%s_candidates)' % len(tpts))
        r.format(q.op)

    return

def annotate_mnv_protein(args, q, tpts, db):

    found = False
    for t in tpts:
        try:
            if q.tpt and t.name != q.tpt:
                raise IncompatibleTranscriptError("Transcript name unmatched")
            t.ensure_seq()

            r = Record()
            r.chrm = t.chrm
            r.tname = t.format()
            r.gene = t.gene.name
            r.strand = t.strand

            if q.beg*3 > len(t) or q.end*3 > len(t):
                raise IncompatibleTranscriptError('codon nonexistent')

            tnuc_beg = q.beg*3-2
            tnuc_end = q.end*3
            gnuc_beg, gnuc_end = t.tnuc_range2gnuc_range(tnuc_beg, tnuc_end)
            tnuc_refseq = t.seq[tnuc_beg-1:tnuc_end]
            gnuc_refseq = reverse_complement(tnuc_refseq) if t.strand == '-' else tnuc_refseq
            taa_refseq = translate_seq(tnuc_refseq)
            if q.beg_aa and q.beg_aa != taa_refseq[0]:
                raise IncompatibleTranscriptError('beginning reference amino acid unmatched')
            if q.end_aa and q.end_aa != taa_refseq[-1]:
                raise IncompatibleTranscriptError('ending reference amino acid unmatched')
            if q.refseq and taa_refseq != q.refseq:
                raise IncompatibleTranscriptError('reference sequence unmatched')
            # reverse translate
            tnuc_altseq = []
            cdd_altseq = []
            for aa in q.altseq:
                tnuc_altseq.append(aa2codon(aa)[0])
                cdd_altseq.append('/'.join(aa2codon(aa)))
            tnuc_altseq = ''.join(tnuc_altseq)
            gnuc_altseq = reverse_complement(tnuc_altseq) if t.strand == '-' else tnuc_altseq
            r.tnuc_range = '%d_%d%s>%s' % (tnuc_beg, tnuc_end, tnuc_refseq, tnuc_altseq)
            r.gnuc_range = '%d_%d%s>%s' % (gnuc_beg, gnuc_end, gnuc_refseq, gnuc_altseq)
            r.pos = '%d-%d' % (gnuc_beg, gnuc_end)
            if len(cdd_altseq) <= 2:
                r.append_info('candidate_alternative_sequence=%s' % ('+'.join(cdd_altseq), ))

        except IncompatibleTranscriptError:
            continue
        except UnknownChromosomeError:
            continue
        r.taa_range = '%s%s_%s%sdel%sins%s' % (
            q.beg_aa, str(q.beg), q.end_aa, str(q.end), q.refseq, q.altseq)
        r.reg = RegCDSAnno(t)
        r.reg.from_taa_range(q.beg, q.end)
        r.append_info('imprecise')
        r.format(q.op)
        found = True

    if not found:
        r = Record()
        r.taa_range = '%s%s_%s%sdel%sins%s' % (
            q.beg_aa, str(q.beg), q.end_aa, str(q.end), q.refseq, q.altseq)
        r.append_info('no_valid_transcript_found_(from_%s_candidates)' % len(tpts))

        r.format(q.op)


def annotate_mnv_gdna(args, q, db):

    # check reference sequence
    gnuc_refseq = faidx.refgenome.fetch_sequence(q.tok, q.beg, q.end)
    if q.refseq and gnuc_refseq != q.refseq:
        
        r = Record()
        r.chrm = q.tok
        r.pos = '%d-%d' % (q.beg, q.end)
        r.info = "invalid_reference_seq_%s_(expect_%s)" % (q.refseq, gnuc_refseq)
        r.format(q.op)
        err_print("Warning: %s invalid reference %s (expect %s), maybe wrong reference?" % (q.op, q.refseq, gnuc_refseq))
        return
    
    else:                       # make sure q.refseq exists
        q.refseq = gnuc_refseq

    for reg in describe(args, q, db):

        r = Record()
        r.reg = reg
        r.chrm = q.tok
        r.pos = '%d-%d' % (q.beg, q.end)
        r.gnuc_refseq = q.refseq
        r.gnuc_altseq = q.altseq
        r.gnuc_range = '%d_%d%s>%s' % (q.beg, q.end, r.gnuc_refseq, r.gnuc_altseq)

        if hasattr(reg, 't'):

            t = reg.t
            r.tname = t.format()
            r.gene = t.gene.name
            r.strand = t.strand

            c1, p1 = t.gpos2codon(q.beg, intronic_policy="g_greater")
            c2, p2 = t.gpos2codon(q.end, intronic_policy="g_smaller")

            if t.strand == '+':
                tnuc_beg = p1
                tnuc_end = p2
                tnuc_refseq = q.refseq
                tnuc_altseq = q.altseq
            else:
                tnuc_beg = p2
                tnuc_end = p1
                tnuc_refseq = reverse_complement(q.refseq)
                tnuc_altseq = reverse_complement(q.altseq)
            r.tnuc_range = '%s_%s%s>%s' % (tnuc_beg, tnuc_end, tnuc_refseq, tnuc_altseq)

            if r.reg.entirely_in_cds():
                try:
                    tnuc_mnv_coding(t, tnuc_beg.pos, tnuc_end.pos, tnuc_altseq, r)
                except IncompatibleTranscriptError as inst:
                    _beg, _end, _seqlen = inst
                    r.append_info('mnv_(%s-%s)_at_truncated_refseq_of_length_%d' % (_beg, _end, _seqlen))

        elif isinstance(reg, RegSpanAnno):

            tnames = []
            strands = []
            genes = []
            if hasattr(reg.b1, 't'):
                if reg.b1.t.name not in tnames:
                    tnames.append(reg.b1.t.name)
                    strands.append(reg.b1.t.strand)
                    genes.append(reg.b1.t.gene.name)
                    
            if hasattr(reg.b2, 't'):
                if reg.b2.t.name not in tnames:
                    tnames.append(reg.b2.t.name)
                    strands.append(reg.b2.t.strand)
                    genes.append(reg.b2.t.gene.name)

            r.tname = ','.join(tnames)
            r.strand = ','.join(strands)
            r.gene = ','.join(genes)

        r.format(q.op)


def tnuc_mnv_coding(t, beg, end, altseq, r):

    if (len(altseq) - (end-beg+1)) % 3 == 0: # in frame

        # beg and end are integer tnuc positions
        # altseq follows the tnuc (cDNA) order
        # set taa range

        beg_codon_index = (beg + 2) / 3
        end_codon_index = (end + 2) / 3

        beg_codon_beg = beg_codon_index*3 - 2
        end_codon_end = end_codon_index*3 # 1 past the last codon

        old_seq = t.seq[beg_codon_beg-1:end_codon_end]
        new_seq = t.seq[beg_codon_beg-1:beg-1]+altseq+t.seq[end:end_codon_end]

        if beg_codon_index == end_codon_index:
            r.append_info('codon_cDNA=%s' % '-'.join(map(str, range(beg_codon_beg, beg_codon_beg+3))))
        else:
            r.append_info('begin_codon_cDNA=%s' % '-'.join(map(str, range(beg_codon_beg, beg_codon_beg+3))))
            r.append_info('end_codon_cDNA=%s' % '-'.join(map(str, range(end_codon_end-2, end_codon_end+1))))

        if len(old_seq) % 3 != 0:
            raise IncompatibleTranscriptError(beg, end, len(t.seq))

        old_taa_seq = translate_seq(old_seq)
        new_taa_seq = translate_seq(new_seq)
        if old_taa_seq == new_taa_seq:
            r.taa_range = '(=)'
            return

        # block substitution in nucleotide level may end up
        # an insertion or deletion on the protein level
        old_taa_seq1, new_taa_seq1, head_trim, tail_trim = double_trim(old_taa_seq, new_taa_seq)
        if not old_taa_seq1:
            _beg_index = beg_codon_index + head_trim - 1
            _end_index = beg_codon_index + head_trim
            _beg_aa = codon2aa(t.seq[_beg_index*3-3:_beg_index*3])
            _end_aa = codon2aa(t.seq[_end_index*3-3:_end_index*3])
            taa_set_ins(r, t, _beg_index, new_taa_seq1)
            return

        if not new_taa_seq1:
            taa_set_del(r, t, beg_codon_index+head_trim, end_codon_index-tail_trim)
            return

        if len(old_taa_seq1) == 1:
            if len(new_taa_seq1) == 1:
                r.taa_range = '%s%d%s' % (
                    old_taa_seq1[0], beg_codon_index + head_trim, new_taa_seq1)
                return
            else:
                r.taa_range = '%s%ddelins%s' % (
                    old_taa_seq1[0], beg_codon_index + head_trim, new_taa_seq1)
                return

        r.taa_range = '%s%d_%s%ddelins%s' % (
            old_taa_seq1[0], beg_codon_index + head_trim,
            old_taa_seq1[-1], end_codon_index - tail_trim, new_taa_seq1)

    else:                   # frame-shift

        beg_codon_index = (beg + 2) / 3
        beg_codon_beg = beg_codon_index * 3 - 2
        old_seq = t.seq[beg_codon_beg-1:]
        new_seq = t.seq[beg_codon_beg-1:beg-1]+altseq+t.seq[end:]

        ret = t.extend_taa_seq(beg_codon_index, old_seq, new_seq)
        if ret:
            taa_pos, taa_ref, taa_alt, termlen = ret
            r.taa_range = '%s%d%sfs*%s' % (taa_ref, taa_pos, taa_alt, termlen)
        else:
            r.taa_range = '(=)'